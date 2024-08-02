import json
import traceback

from typing import List, Optional
from uuid import uuid4

from pylon.core.tools import web, log

from langchain_openai import AzureChatOpenAI
from pydantic import parse_obj_as, ValidationError
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from ..models.enums.all import PromptVersionType
from ..models.pd.predict import PromptVersionPredictModel
from ..utils.ai_providers import AIProvider
from ..models.pd.v1_structure import PromptV1Model, TagV1Model
from tools import rpc_tools, db, auth
from ..models.all import (
    Prompt,
    PromptVersion,
)
from ..utils.conversation import prepare_payload, prepare_conversation, CustomTemplateError, \
    convert_messages_to_langchain
from ...promptlib_shared.utils.constants import PredictionEvents
from ...promptlib_shared.utils.sio_utils import SioValidationError, get_event_room, SioEvents
from ...integrations.models.pd.integration import SecretField


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
                if messages[idx]['role'] == 'user' and messages[idx + 1]['role'] == 'assistant':
                    examples.append({
                        "id": None,  # TODO: We have no example id anymore. Need to be fixed somehow.
                        "prompt_id": result.get('prompt_id'),
                        "input": messages[idx]['content'],
                        "output": messages[idx + 1]['content'],
                        "is_active": True,
                        "created_at": messages[idx + 1]['created_at']
                    })

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
        if payload.integration.name == "ai_preload_shim":
            log.info(f'{payload.merged_settings=}')
            #
            routing_key = payload.merged_settings["model_name"]
            call_messages = json.loads(json.dumps(conversation))
            call_kwargs = {
                "max_new_tokens": payload.merged_settings["max_tokens"],
                "return_full_text": False,
                "temperature": payload.merged_settings["temperature"],
                "do_sample": True,
                "top_k": payload.merged_settings["top_k"],
                "top_p": payload.merged_settings["top_p"],
            }
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
                    "content": {**start_event_content}
                },
                room=room,
            )
            #
            from tools import worker_client  # pylint: disable=E0401,C0415
            #
            task_id = worker_client.task_node.start_task(
                name="invoke_model",
                kwargs={
                    "routing_key": routing_key,
                    "method": "__call__",
                    "method_args": [call_messages],
                    "method_kwargs": call_kwargs,
                },
                pool="indexer",
            )
            #
            log.info("Router task: %s", task_id)
            #
            try:
                full_result = worker_client.task_node.join_task(task_id)[0]["generated_text"]
            except:  # pylint: disable=W0702
                full_result = traceback.format_exc()
            #
            chunk_data = {
                "type": "AIMessageChunk",
                "content": full_result,
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
            # For now:
            # - No streaming
            # - No monitoring calls
        else:
            #
            # AzureChatOpenAI
            #
            api_token = SecretField.parse_obj(payload.merged_settings["api_token"])
            try:
                api_token = api_token.unsecret(payload.integration.project_id)
            except AttributeError:
                api_token = api_token.unsecret(None)
            #
            try:
                from tools import context
                module = context.module_manager.module.open_ai_azure
                #
                if module.ad_token_provider is None:
                    raise RuntimeError("No AD provider, using token")
                #
                ad_token_provider = module.ad_token_provider
            except:
                ad_token_provider = None
            #
            try:
                if ad_token_provider is None:
                    chat = AzureChatOpenAI(
                        api_key=api_token,
                        azure_endpoint=payload.merged_settings['api_base'],
                        azure_deployment=payload.merged_settings['model_name'],
                        api_version=payload.merged_settings['api_version'],
                        streaming=True
                    )
                else:
                    chat = AzureChatOpenAI(
                        azure_ad_token_provider=ad_token_provider,
                        azure_endpoint=payload.merged_settings['api_base'],
                        azure_deployment=payload.merged_settings['model_name'],
                        api_version=payload.merged_settings['api_version'],
                        streaming=True
                    )
            except:
                if ad_token_provider is None:
                    chat = AzureChatOpenAI(
                        openai_api_key=api_token,
                        openai_api_base=payload.merged_settings['api_base'],
                        deployment_name=payload.merged_settings['model_name'],
                        openai_api_version=payload.merged_settings['api_version'],
                        streaming=True
                    )
                else:
                    chat = AzureChatOpenAI(
                        azure_ad_token_provider=ad_token_provider,
                        openai_api_base=payload.merged_settings['api_base'],
                        deployment_name=payload.merged_settings['model_name'],
                        openai_api_version=payload.merged_settings['api_version'],
                        streaming=True
                    )
            #
            conversation = convert_messages_to_langchain(conversation)
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
                    "content": {**start_event_content}
                },
                room=room,
            )
            #
            full_result = ""
            #
            for chunk in chat.stream(input=conversation, config=payload.merged_settings):
                chunk_data = chunk.dict()
                full_result += chunk_data["content"]
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
            tokens_in = chat.get_num_tokens(full_result)
            tokens_out = chat.get_num_tokens_from_messages(conversation)
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
