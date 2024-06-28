from typing import List, Optional
from uuid import uuid4

from pylon.core.tools import web, log

from langchain_openai import AzureChatOpenAI
from pydantic import parse_obj_as, ValidationError
from sqlalchemy.orm import joinedload
from ..models.enums.all import PromptVersionType
from ..models.pd.predict import PromptVersionPredictModel

from ..utils.ai_providers import AIProvider
from ..models.pd.v1_structure import PromptV1Model, TagV1Model
from tools import rpc_tools, db
from ..models.all import (
    Prompt,
    PromptVersion,
)
from ..utils.conversation import prepare_payload, prepare_conversation, CustomTemplateError
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
    def prompts_get_by_version_id(self, project_id: int, prompt_id: int, version_id: int = None, **kwargs) -> dict | None:

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
    def prompts_get_by_id(self, project_id: int, prompt_id: int, version: str = 'latest', **kwargs) -> dict | None:
        with db.with_project_schema_session(project_id) as session:
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
                return None

            result = prompt_version.to_json()
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
    def predict_sio(self, sid: str, data: dict, sio_event: str = SioEvents.promptlib_predict,
                    start_event_content: Optional[dict] = None
                    ):
        if start_event_content is None:
            start_event_content = {}
        data['message_id'] = data.get('message_id', str(uuid4()))
        data['stream_id'] = data.get('stream_id', data['message_id'])
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

        log.info(f'{conversation=}')
        log.info(f'{payload.merged_settings=}')
        api_token = SecretField.parse_obj(payload.merged_settings["api_token"])
        try:
            api_token = api_token.unsecret(payload.integration.project_id)
        except AttributeError:
            api_token = api_token.unsecret(None)

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
            from langchain.schema import (
                AIMessage,
                HumanMessage,
                SystemMessage,
            )
            from ..models.enums.all import MessageRoles
            #
            new_conversation = conversation
            conversation = []
            #
            for item in new_conversation:
                if item["role"] == MessageRoles.assistant:
                    conversation.append(AIMessage(content=item["content"]))
                elif item["role"] == MessageRoles.user:
                    conversation.append(HumanMessage(content=item["content"]))
                elif item["role"] == MessageRoles.system:
                    conversation.append(SystemMessage(content=item["content"]))

        room = get_event_room(
            event_name=sio_event,
            room_id=payload.stream_id
        )
        if sid:
            self.context.sio.enter_room(sid, room)
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

        full_result = ""

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

        if sio_event == SioEvents.chat_predict:
            chat_payload = {
                'message_id': payload.message_id,
                'response_metadata': {
                    'project_id': payload.project_id
                },
                'content': full_result,
            }
            self.context.event_manager.fire_event('chat_message_stream_end', chat_payload)

        try:
            from tools import auth, monitoring
            #
            count_conversation = []
            #
            from langchain_core.messages import (
                AIMessage,
                HumanMessage,
                SystemMessage,
            )
            from ..models.enums.all import MessageRoles
            #
            for item in conversation:
                if item["role"] == MessageRoles.assistant:
                    count_conversation.append(AIMessage(
                        content=item["content"],
                        name=item.get("name", None),
                    ))
                elif item["role"] == MessageRoles.user:
                    count_conversation.append(HumanMessage(
                        content=item["content"],
                        name=item.get("name", None),
                    ))
                elif item["role"] == MessageRoles.system:
                    count_conversation.append(SystemMessage(
                        content=item["content"],
                        name=item.get("name", None),
                    ))
            #
            tokens_out = chat.get_num_tokens(full_result)
            tokens_in = chat.get_num_tokens_from_messages(count_conversation)
            #
            current_user = auth.current_user(
                auth_data=auth.sio_users[sid]
            )
            #
            project_id = payload.project_id
            #
            entity_type = "prompt"
            entity_id = data.get("prompt_id", None)
            entity_version = data.get("prompt_version_id", None)
            #
            monitoring.prompt_complete(
                user_id=current_user["id"],
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_version=entity_version,
                conversation=conversation,
                predict_result=full_result,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        except:
            log.exception("Ignoring monitoring error")

#     @web.rpc("prompts_get_examples_by_prompt_id", "get_examples_by_prompt_id")
#     def prompts_get_examples_by_prompt_id(
#             self, project_id: int, prompt_id: int, **kwargs
#     ) -> list[dict]:
#         with db.with_project_schema_session(project_id) as session:
#             examples = session.query(Example).filter(Example.prompt_id == prompt_id).all()
#             return [example.to_json() for example in examples]

#     @web.rpc(f'prompts_create_example', "create_example")
#     def prompts_create_example(self, project_id: int, example: dict, from_test_input: bool = False, **kwargs) -> dict:
#         example = ExampleModel.validate(example)
#         with db.with_project_schema_session(project_id) as session:
#             example = Example(**example.dict())
#             session.add(example)
#             if from_test_input:
#                 session.query(Prompt).filter(Prompt.id == example.prompt_id).update(
#                     {'test_input': None}
#                 )
#             session.commit()
#             return example.to_json()

#     @web.rpc(f'prompts_create_examples_bulk', "create_examples_bulk")
#     def prompts_create_examples_bulk(self, project_id: int, examples: List[dict], **kwargs) -> None:
#         examples = parse_obj_as(List[ExampleModel], examples)
#         with db.with_project_schema_session(project_id) as session:
#             for i in examples:
#                 example = Example(**i.dict())
#                 session.add(example)
#             session.commit()

#     @web.rpc(f'prompts_update_example', "update_example")
#     def prompts_update_example(self, project_id: int, example: dict, **kwargs) -> bool:
#         example = ExampleUpdateModel.validate(example)
#         with db.with_project_schema_session(project_id) as session:
#             session.query(Example).filter(Example.id == example.id).update(
#                 example.dict(exclude={'id'}, exclude_none=True)
#             )
#             session.commit()
#             updated_example = session.query(Example).get(example.id)
#             return updated_example.to_json()

#     @web.rpc(f'prompts_delete_example', "delete_example")
#     def prompts_delete_example(self, project_id: int, example_id: int, **kwargs) -> bool:
#         with db.with_project_schema_session(project_id) as session:
#             example = session.query(Example).get(example_id)
#             if example:
#                 session.delete(example)
#                 session.commit()
#             return True

#     @web.rpc("prompts_get_versions_by_prompt_name", "get_versions_by_prompt_name")
#     def prompts_get_versions_by_prompt_name(self, project_id: int, prompt_name: str) -> list[dict]:
#         with db.with_project_schema_session(project_id) as session:
#             prompts = session.query(Prompt).filter(
#                 Prompt.name == prompt_name
#             ).order_by(
#                 Prompt.version
#             ).all()
#             return [prompt.to_json() for prompt in prompts]

#     @web.rpc("prompts_get_ai_provider", "get_ai_provider")
#     def prompts_get_ai_provider(self) -> AIProvider:
#         return AIProvider

#     @web.rpc(f'prompts_prepare_prompt_struct', "prepare_prompt_struct")
#     def prompts_prepare_prompt_struct(self, project_id: int, prompt_id: Optional[int],
#                                       input_: str = '', context: str = '', examples: list = [],
#                                       variables: dict = {}, ignore_template_error: bool = False,
#                                       chat_history: Optional[dict] = None, addons: Optional[dict] = None,
#                                       **kwargs) -> dict:

#         # example_template = '\ninput: {input}\noutput: {output}'

#         prompt_struct = {
#             "context": context,
#             "examples": examples,  # list of dicts {"input": "value", "output": "value"}
#             "variables": variables,  # list of dicts {"var_name": "value"}
#             "prompt": input_
#         }
#         if chat_history:
#             prompt_struct['chat_history'] = chat_history
#         if addons:
#             prompt_struct['addons'] = addons
#         if prompt_id:
#             prompt_template = self.get_by_id(project_id, prompt_id)
#             if not prompt_template:
#                 raise Exception(f"Prompt with id {prompt_id} in project {project_id} not found")
#             prompt_struct['context'] = prompt_template['prompt'] + prompt_struct['context']
#             for example in prompt_template['examples']:
#                 if not example['is_active']:
#                     continue
#                 prompt_struct['examples'].append({
#                     "input": example['input'],
#                     "output": example['output']
#                 })
#             for variable in prompt_template['variables']:
#                 if not prompt_struct['variables'].get(variable['name']):
#                     prompt_struct['variables'][variable['name']] = variable['value']
#             # if prompt_struct['prompt']:
#             #     prompt_struct['variables']['prompt'] = prompt_struct['prompt']

#         prompt_struct = resolve_variables(prompt_struct, ignore_template_error=ignore_template_error)
#         prompt_struct.pop('variables')

#         # for example in prompt_struct['examples']:
#         #     prompt_struct['context'] += example_template.format(**example)

#         # if prompt_struct['prompt']:
#         #     prompt_struct['context'] += example_template.format(input=prompt_struct['prompt'], output='')

#         # if prompt_struct['prompt']:
#         #     prompt_struct['prompt'] = example_template.format(input=prompt_struct['prompt'], output='')
#         log.info(f"FINAL: {prompt_struct=}")
#         return prompt_struct


# def resolve_variables(prompt_struct: dict, ignore_template_error: bool = False) -> dict:
#     try:
#         environment = Environment(undefined=DebugUndefined)
#         ast_c = environment.parse(prompt_struct['context'])
#         ast_p = environment.parse(prompt_struct['prompt'])
#         if len(set(meta.find_undeclared_variables(ast_p))) > 0:
#             template_p = environment.from_string(prompt_struct['prompt'])
#             prompt_struct['prompt'] = template_p.render(**prompt_struct['variables'])

#         if 'prompt' in set(meta.find_undeclared_variables(ast_c)):
#             prompt_struct['variables']['prompt'] = prompt_struct['prompt']
#             prompt_struct['prompt'] = ''

#         template = environment.from_string(prompt_struct['context'])
#         prompt_struct['context'] = template.render(**prompt_struct['variables'])

#     except:
#         log.critical(format_exc())
#         if not ignore_template_error:
#             raise Exception("Invalid jinja template in context")

#     return prompt_struct
