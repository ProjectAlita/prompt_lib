import json
import traceback

from typing import List, Optional, Tuple
from uuid import uuid4

from pylon.core.tools import web, log

from pydantic import parse_obj_as, ValidationError
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from ..models.enums.all import PromptVersionType
from ..models.pd.export_import import PromptImportModel
from ..models.pd.predict import PromptVersionPredictModel
from ..models.pd.prompt import PromptDetailModel
from ..utils.ai_providers import AIProvider
from ..models.pd.v1_structure import PromptV1Model, TagV1Model
from tools import rpc_tools, db, auth
from ..models.all import (
    Prompt,
    PromptVersion,
)
from ..utils.conversation import prepare_payload, prepare_conversation, CustomTemplateError, \
    convert_messages_to_langchain
from ..utils.create_utils import create_prompt
from ...promptlib_shared.utils.constants import PredictionEvents
from ...promptlib_shared.utils.sio_utils import SioValidationError, get_event_room, SioEvents
from ..utils.export_import_utils import prompts_export


class RPC:
    @web.rpc(f'prompt_lib_get_all', "get_all")
    def prompt_lib_get_all(self, project_id: int, with_versions: bool = False, **kwargs) -> List[dict]:
        # TODO: Support with_versions flag if we still need it
        with db.with_project_schema_session(project_id) as session:
            queryset = session.query(Prompt).order_by(Prompt.id.asc()).all()
            prompts = []
            for prompt in queryset:
                result = prompt.to_json()
                result['versions'] = []
                for v in prompt.versions:
                    v_data = v.to_json()
                    v_data['tags'] = []
                    for i in v.tags:
                        v_data['tags'].append(i.to_json())
                    result['versions'].append(v_data)
                prompts.append(result)

            results = parse_obj_as(List[PromptV1Model], prompts)
            return [prompt.dict() for prompt in results]

    @web.rpc("prompt_lib_get_by_version_id", "get_by_version_id")
    def prompts_get_by_version_id(self, project_id: int, prompt_id: int, version_id: int = None,
                                  **kwargs) -> dict | None:

        if version_id is None:
            version_name = "latest"
        else:
            with db.with_project_schema_session(project_id) as session:
                prompt_version = session.query(PromptVersion).filter(
                    PromptVersion.id == version_id
                ).one_or_none()

                if not prompt_version:
                    return None

                version_name = prompt_version.name

        result = self.get_by_id(project_id, prompt_id, version_name)

        result['version_id'] = version_id
        if version_id is None:
            for v in result['versions']:
                if version_name == v['version']:
                    result['version_id'] = v['id']
                    break
            else:
                raise RuntimeError(f"No version_id found for prompt {version_name}")

        return result

    @web.rpc("prompt_lib_get_by_id", "get_by_id")
    def prompts_get_by_id(self, project_id: int, prompt_id: int, version: str = 'latest',
                          first_existing_version: bool = False, **kwargs) -> dict | None:
        with db.get_session(project_id) as session:
            prompt_version = session.query(PromptVersion).options(
                joinedload(PromptVersion.prompt)
            ).options(
                joinedload(PromptVersion.variables)
            ).options(
                joinedload(PromptVersion.messages)
            ).filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.name == version
            ).one_or_none()
            if not prompt_version:
                if not first_existing_version:
                    return None
                prompt_version = session.query(PromptVersion).options(
                    joinedload(PromptVersion.prompt)
                ).options(
                    joinedload(PromptVersion.variables)
                ).options(
                    joinedload(PromptVersion.messages)
                ).filter(
                    PromptVersion.prompt_id == prompt_id,
                ).order_by(
                    desc(PromptVersion.created_at)
                ).first()

            result = prompt_version.to_json()
            result['version_id'] = prompt_version.id
            result['id'] = prompt_version.prompt.id
            result['version'] = result['name']
            result['name'] = prompt_version.prompt.name
            result['prompt'] = result.pop('context')

            model_settings = result.get('model_settings')
            if model_settings:
                if integration_uid := model_settings.get('model', {}).get('integration_uid'):
                    whole_settings = AIProvider.get_integration_settings(
                        project_id, integration_uid, prompt_version.model_settings
                    )
                    result['model_settings'] = whole_settings
                    result['integration_uid'] = integration_uid if whole_settings else None

            messages = [example.to_json() for example in prompt_version.messages]
            examples = []
            for idx in range(0, len(messages), 2):
                try:
                    if messages[idx]['role'] == 'user' and messages[idx + 1]['role'] == 'assistant':
                        examples.append({
                            "id": None,  # TODO: We have no example id anymore. Need to be fixed somehow.
                            "prompt_id": result.get('prompt_id'),
                            "input": messages[idx]['content'],
                            "output": messages[idx + 1]['content'],
                            "is_active": True,
                            "created_at": messages[idx + 1]['created_at']
                        })
                except IndexError:
                    ...

            result['examples'] = examples
            result['variables'] = [var.to_json() for var in prompt_version.variables]
            result['tags'] = [TagV1Model(**tag.to_json()).dict() for tag in prompt_version.tags]
            result['versions'] = [{
                'id': version.id,
                'version': version.name,
                'tags': [tag.name for tag in version.tags]
            } for version in prompt_version.prompt.versions]

            return result

    @web.rpc("prompt_lib_predict_sio", "predict_sio")
    def predict_sio(self,
                    sid: str,
                    data: dict,
                    sio_event: str = SioEvents.promptlib_predict.value,
                    start_event_content: Optional[dict] = None,
                    chat_project_id: Optional[int] = None
                    ):
        #
        if start_event_content is None:
            start_event_content = {}
        #
        data['message_id'] = data.get('message_id', str(uuid4()))
        data['stream_id'] = data.get('stream_id', data['message_id'])
        #
        try:
            payload: PromptVersionPredictModel = prepare_payload(data=data)
        except ValidationError as e:
            raise SioValidationError(
                sio=self.context.sio,
                sid=sid,
                event=sio_event,
                error=e.errors(),
                stream_id=data.get("stream_id"),
                message_id=data.get("message_id")
            )
        #
        try:
            conversation = prepare_conversation(payload=payload)
        except CustomTemplateError as e:
            raise SioValidationError(
                sio=self.context.sio,
                sid=sid,
                event=sio_event,
                error=e.errors(),
                stream_id=payload.stream_id,
                message_id=payload.message_id,
            )
        except Exception as e:
            log.exception("prepare_conversation")
            raise SioValidationError(
                sio=self.context.sio,
                sid=sid,
                event=sio_event,
                error={'ok': False, 'msg': str(e), 'loc': []},
                stream_id=payload.stream_id,
                message_id=payload.message_id
            )
        #
        room = get_event_room(
            event_name=sio_event,
            room_id=payload.stream_id
        )
        #
        if sid:
            self.context.sio.enter_room(sid, room)
        #
        self.context.sio.emit(
            event=sio_event,
            data={
                "stream_id": payload.stream_id,
                "message_id": payload.message_id,
                "type": "start_task",
                "message_type": payload.type,
                "content": {**start_event_content},
                'interaction_uuid': payload.interaction_uuid
            },
            room=room,
        )
        #
        full_result = ""
        #
        from tools import worker_client  # pylint: disable=E0401,C0415
        #
        try:
            for chunk in worker_client.chat_model_stream(
                integration_name=payload.integration.name,
                settings=payload,
                messages=conversation,
            ):
                full_result += chunk["content"]
                #
                chunk_data = {
                    "type": "AIMessageChunk",
                    "content": chunk["content"],
                    "response_metadata": {},
                }
                #
                chunk_data['stream_id'] = payload.stream_id
                chunk_data['message_id'] = payload.message_id
                #
                if payload.type == PromptVersionType.freeform:
                    chunk_data['message_type'] = PromptVersionType.freeform
                #
                self.context.sio.emit(
                    event=sio_event,
                    data=chunk_data,
                    room=room,
                )
        except BaseException as exception:  # pylint: disable=W0718
            exception_info = str(exception)
            #
            self.context.sio.emit(
                event=sio_event,
                data={
                    "type": "AIMessageChunk",
                    "content": f"⚠ Predict exception: {exception_info}",
                    "response_metadata": {},
                    "stream_id": payload.stream_id,
                    "message_id": payload.message_id,
                },
                room=room,
            )
        #
        self.context.sio.emit(
            event=sio_event,
            data={
                "type": "AIMessageChunk",
                "content": "",
                "response_metadata": {
                    "finish_reason": "stop",
                },
                "stream_id": payload.stream_id,
                "message_id": payload.stream_id,
            },
            room=room,
        )
        #
        if sio_event == SioEvents.chat_predict.value and chat_project_id is not None:
            chat_payload = {
                'message_id': payload.message_id,
                'response_metadata': {
                    'project_id': payload.project_id,
                    'chat_project_id': chat_project_id,
                },
                'content': full_result,
            }
            self.context.event_manager.fire_event('chat_message_stream_end', chat_payload)
        #
        current_user = auth.current_user(
            auth_data=auth.sio_users[sid]
        )
        #
        tokens_in = worker_client.ai_count_tokens(
            integration_name=payload.integration.name,
            settings=payload,
            data=full_result,
        )
        #
        tokens_out = worker_client.ai_count_tokens(
            integration_name=payload.integration.name,
            settings=payload,
            data=conversation,
        )
        #
        conversation = convert_messages_to_langchain(conversation)
        #
        event_payload = {
            'pylon': str(self.context.id),
            'project_id': payload.project_id,
            'user_id': current_user["id"],
            'predict_source': str(sio_event),
            'entity_type': 'prompt',
            'entity_id': payload.prompt_id,
            'entity_meta': {'version_id': payload.prompt_version_id, 'prediction_type': payload.type},
            'chat_history': [i.dict() for i in conversation],
            'predict_response': full_result,
            'model_settings': payload.merged_settings,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'interaction_uuid': payload.interaction_uuid
        }
        #
        self.context.event_manager.fire_event(
            PredictionEvents.prediction_done,
            json.loads(json.dumps(event_payload))
        )

    @web.rpc("prompt_lib_get_prompt_model", "get_prompt_model")
    def get_prompt_model(self):
        return Prompt

    @web.rpc("prompt_lib_get_version_model", "get_version_model")
    def get_version_model(self):
        return PromptVersion

    @web.rpc("prompt_lib_import_prompt", "import_prompt")
    def import_prompt(self, raw: dict, project_id: int, author_id: int) -> Tuple[str, list]:
        errors = []

        with db.with_project_schema_session(project_id) as session:
            raw['owner_id'] = project_id
            for version in raw.get("versions", []):
                meta = version.get('meta') or {}
                if 'parent_author_id' in meta:
                    version["author_id"] = meta.get('parent_author_id')
                else:
                    version["author_id"] = author_id
                if not version.get('name'):
                    version['name'] = 'latest'
            try:
                prompt_data = PromptImportModel.parse_obj(raw)
            except ValidationError as e:
                errors.append(str(e))
                return '', errors
            prompt = create_prompt(prompt_data, session)
            session.commit()

            return json.loads(PromptDetailModel.from_orm(prompt).json()), errors

    @web.rpc("prompt_lib_export_prompt")
    def export_prompt(self, prompts_grouped: dict, forked: bool = False) -> dict:
        result = {
            'prompts': []
        }
        for project_id, prompt_ids in prompts_grouped.items():
            for prompt_id in prompt_ids:
                result['prompts'].extend(
                    prompts_export(project_id, prompt_id, forked=forked).get('prompts', [])
                )
        return result

    @web.rpc("prompt_lib_update_tool_with_existing_fork", "update_tool_with_existing_fork")
    def prompt_lib_update_tool_with_existing_fork(
            self, target_project_id: int, input_tool: dict,
            tool_parent_entity_id: int, tool_parent_project_id: int
    ) -> Tuple[dict, str]:
        with db.get_session(target_project_id) as session:
            is_forked_subquery = (
                session.query(PromptVersion.prompt_id)
                .filter(PromptVersion.meta.op('->>')('parent_entity_id').isnot(None),
                        PromptVersion.meta.op('->>')('parent_project_id').isnot(None))
                .subquery()
            )
            target_project_forked_prompts = session.query(Prompt).filter(
                Prompt.id.in_(is_forked_subquery)
            ).all()

            for forked_prompt in target_project_forked_prompts:
                for version in forked_prompt.versions:
                    forked_version_meta = version.meta or {}
                    forked_version_parent_entity_id = forked_version_meta.get('parent_entity_id')
                    forked_version_parent_project_id = forked_version_meta.get('parent_project_id')
                    if tool_parent_entity_id == forked_version_parent_entity_id \
                            and tool_parent_project_id == forked_version_parent_project_id:
                        input_tool['settings'].pop('import_uuid')
                        import_version_uuid = input_tool['settings'].pop('import_version_uuid')
                        input_tool.update({
                            'prompt_version_id': version.id,
                            'prompt_id': forked_prompt.id,
                        })
                        return input_tool, import_version_uuid
            else:
                return input_tool, str()
