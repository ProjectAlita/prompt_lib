from typing import Optional

from flask import request
from pylon.core.tools import log
import tiktoken
from ...models.enums.all import MessageRoles

try:
    from langchain_openai import AzureChatOpenAI
except:
    from langchain.chat_models import AzureChatOpenAI
from pydantic import ValidationError
from ....integrations.models.pd.integration import SecretField
from ...models.all import PromptVersion, Prompt
from ...models.pd.legacy.prompts_pd import PredictPostModel
from ...utils.ai_providers import AIProvider
from traceback import format_exc

from tools import api_tools, db, auth, config as c

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.conversation import prepare_conversation, CustomTemplateError, prepare_payload


# TODO add more models or find an API to get tokens limit
MODEL_TOKENS_MAPPER = {
    "text-davinci-003": 4097,
    "text-davinci-002": 4097,
    "anthropic.claude-v2": 100_000,
    "gpt-35-turbo": 4096,
    "gpt-35-turbo16k": 16384,
    "gpt-4": 8192,
    "gpt-4-0613": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-32k-0613": 32768,
    "text-bison@001": 8192,
    "text-bison": 8192,
    "stability.stable-diffusion-xl": 77,
    "gpt-world": 24000,
    "epam10k-semantic-search": 24000,
    "statgptpy": 24000,
    "default": 4096
}


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.predict.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, **kwargs):
        payload = dict(request.json)
        log.info("payload **************")
        log.info(payload)
        ignore_template_error = payload.pop('ignore_template_error', False)
        update_prompt = payload.pop('update_prompt', False)
        payload['project_id'] = project_id
        if payload.get('prompt_id') and not all(
                (payload.get('integration_settings'), payload.get('integration_uid'))):
            with db.with_project_schema_session(project_id) as session:
                prompt_version_id = payload['prompt_id']
                prompt_version = session.query(PromptVersion).get(prompt_version_id)
            prompt_version_model_settings = prompt_version.model_settings or {}
            if not payload.get('integration_settings'):
                payload['integration_settings'] = {
                    # todo: handle correct format of integration settings
                }
            if not payload.get('integration_uid'):
                payload['integration_uid'] = prompt_version_model_settings.get('model', {}).get('integration_uid')
        try:
            data = PredictPostModel.parse_obj(payload)
        except Exception as e:
            log.error("************* data = PredictPostModel.parse_obj(payload)")
            log.error(str(e))
            log.info(str(format_exc()))
            log.error("*************")
            return {"error": str(e)}, 400
        model_settings = data.integration_settings.dict(exclude={'project_id'}, exclude_unset=True)

        # todo: handle update prompt
        if update_prompt:
            with db.with_project_schema_session(project_id) as session:
                session.query(Prompt).filter(Prompt.id == data.prompt_id).update(
                    dict(
                        model_settings=model_settings,
                        test_input=data.input_,
                        integration_uid=data.integration_uid
                    )
                )
                session.commit()

        _input = data.input_
        prompt = self.module.get_by_id(project_id, data.prompt_id)
        if prompt:
            _context = prompt["prompt"]
            embedding = prompt.get("embeddings", {})
            if embedding:
                embedding["top_k"] = payload.get("embedding_settings", {}).get("top_k", 20)
                embedding["cutoff"] = payload.get("embedding_settings", {}).get("cutoff", 0.1)
        else:
            _context = data.context
            embedding = {}

        if payload.get("embedding"):
            embedding = payload.get("embedding")

        try:
            if embedding:
                model_name = model_settings["model_name"]
                try:
                    encoding = tiktoken.encoding_for_model(model_name)
                except KeyError:
                    encoding = tiktoken.get_encoding("cl100k_base")
                max_tokens = MODEL_TOKENS_MAPPER.get(model_name, 4000)
                tokens_for_completion = model_settings["max_tokens"]
                tokens_for_context = max_tokens - tokens_for_completion
                results_list = self.module.context.rpc_manager.call.embeddings_similarity_search(project_id,
                                                                                                 embedding["id"],
                                                                                                 _input,
                                                                                                 embedding["top_k"],
                                                                                                 embedding["cutoff"])
                for item in results_list:
                    if len(encoding.encode(item + _context)) <= tokens_for_context:
                        _context += item
                    else:
                        break
                tokens_for_context = len(encoding.encode(_context))
                total_tokens = tokens_for_context + tokens_for_completion
                log.info(f"total_tokens = {total_tokens}")
        except Exception as e:
            log.error(str(e))
            log.info(str(format_exc()))
            log.error("Failed to append embedding to the context")
        try:
            integration = AIProvider.get_integration(
                project_id=project_id,
                integration_uid=data.integration_uid,
            )
            prompt_struct = self.module.prepare_prompt_struct(
                project_id, data.prompt_id, _input,
                _context, data.examples, data.variables,
                chat_history=data.chat_history,
                ignore_template_error=ignore_template_error,
                addons=data.addons
            )
        except Exception as e:
            log.error("************* AIProvider.get_integration and self.module.prepare_prompt_struct")
            log.error(str(e))
            log.info(str(format_exc()))
            log.error("*************")
            return str(e), 400

        result = AIProvider.predict(
            project_id, integration, model_settings, prompt_struct,
            format_response=data.format_response
        )
        if not result['ok']:
            log.error("************* if not result['ok']")
            log.error(str(result['error']))
            log.error("*************")
            return str(result['error']), 400

        if isinstance(result['response'], str):
            result['response'] = {'messages': [{'type': 'text', 'content': result['response']}]}
        return result['response'], 200



class PromptLibAPI(api_tools.APIModeHandler):

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.predict.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, prompt_version_id: Optional[int] = None, **kwargs):

        raw_data = dict(request.json)
        raw_data['project_id'] = project_id
        raw_data['prompt_version_id'] = prompt_version_id
        if 'user_name' not in raw_data:
            user = auth.current_user()
            raw_data['user_name'] = user.get('name')

        try:
            payload = prepare_payload(data=raw_data)
        except ValidationError as e:
            return e.errors(), 400

        try:
            conversation = prepare_conversation(payload=payload)
        except CustomTemplateError as e:
            return e.errors(), 400
        except Exception as e:
            log.exception("prepare_conversation")
            return {'ok': False, 'msg': str(e), 'loc': []}, 400

        log.info(f'{conversation=}')
        log.info(f'{payload.merged_settings=}')
        api_token = SecretField.parse_obj(payload.merged_settings["api_token"])
        try:
            api_token = api_token.unsecret(payload.integration.project_id)
        except AttributeError:
            api_token = api_token.unsecret(None)

        try:
            chat = AzureChatOpenAI(
                api_key=api_token,
                azure_endpoint=payload.merged_settings['api_base'],
                azure_deployment=payload.merged_settings['model_name'],
                api_version=payload.merged_settings['api_version'],
                streaming=False
            )
        except:
            chat = AzureChatOpenAI(
                openai_api_key=api_token,
                openai_api_base=payload.merged_settings['api_base'],
                deployment_name=payload.merged_settings['model_name'],
                openai_api_version=payload.merged_settings['api_version'],
                streaming=False
            )
            #
            from langchain.schema import (
                AIMessage,
                HumanMessage,
                SystemMessage,
            )
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

        try:
            result = chat.invoke(input=conversation, config=payload.merged_settings)
        except Exception as e:
            return {'error': str(e)}, 400

        return {'messages': [result.dict()]}, 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',

        '<string:mode>/<int:project_id>/<int:prompt_version_id>',
        '<int:project_id>/<int:prompt_version_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
