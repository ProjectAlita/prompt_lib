import json
import traceback

from typing import Optional

from flask import request
from pylon.core.tools import log
import tiktoken
from ....promptlib_shared.utils.constants import PredictionEvents

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
from ...utils.conversation import prepare_conversation, CustomTemplateError, prepare_payload, \
    convert_messages_to_langchain

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
        #
        raw_data = dict(request.json)
        raw_data['project_id'] = project_id
        raw_data['prompt_version_id'] = prompt_version_id
        if 'user_name' not in raw_data:
            user = auth.current_user()
            raw_data['user_name'] = user.get('name')
        #
        try:
            payload = prepare_payload(data=raw_data)
        except ValidationError as e:
            return e.errors(), 400
        #
        try:
            conversation = prepare_conversation(payload=payload)
        except CustomTemplateError as e:
            return e.errors(), 400
        except Exception as e:
            log.exception("prepare_conversation")
            return {'ok': False, 'msg': str(e), 'loc': []}, 400
        #
        if payload.integration.name == "ai_preload_shim":
            # log.debug(f'{conversation=}')
            # log.debug(f'{payload.merged_settings=}')
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
            log.debug("Router task: %s", task_id)
            #
            try:
                full_result = worker_client.task_node.join_task(task_id)[0]["generated_text"]
            except:  # pylint: disable=W0702
                full_result = traceback.format_exc()
            #
            result = {
                "type": "text",
                "content": full_result,
            }
            #
            return {"messages": [result]}, 200
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
                        streaming=False
                    )
                else:
                    chat = AzureChatOpenAI(
                        azure_ad_token_provider=ad_token_provider,
                        azure_endpoint=payload.merged_settings['api_base'],
                        azure_deployment=payload.merged_settings['model_name'],
                        api_version=payload.merged_settings['api_version'],
                        streaming=False
                    )
            except:
                if ad_token_provider is None:
                    chat = AzureChatOpenAI(
                        openai_api_key=api_token,
                        openai_api_base=payload.merged_settings['api_base'],
                        deployment_name=payload.merged_settings['model_name'],
                        openai_api_version=payload.merged_settings['api_version'],
                        streaming=False
                    )
                else:
                    chat = AzureChatOpenAI(
                        azure_ad_token_provider=ad_token_provider,
                        openai_api_base=payload.merged_settings['api_base'],
                        deployment_name=payload.merged_settings['model_name'],
                        openai_api_version=payload.merged_settings['api_version'],
                        streaming=False
                    )
            #
            conversation = convert_messages_to_langchain(conversation)
            #
            try:
                result = chat.invoke(input=conversation, config=payload.merged_settings)
            except Exception as e:
                return {'error': str(e)}, 400
            #
            result = result.dict()
            #
            current_user = auth.current_user()
            tokens_in = chat.get_num_tokens(result['content'])
            tokens_out = chat.get_num_tokens_from_messages(conversation)
            event_payload = {
                'pylon': str(self.module.context.id),
                'project_id': payload.project_id,
                'user_id': current_user["id"],
                'predict_source': 'api',
                'entity_type': 'prompt',
                'entity_id': payload.prompt_id,
                'entity_meta': {'version_id': payload.prompt_version_id, 'prediction_type': payload.type},
                'chat_history': [i.dict() for i in conversation],
                'predict_response': result['content'],
                'model_settings': payload.merged_settings,
                'tokens_in': tokens_in,
                'tokens_out': tokens_out,
            }
            self.module.context.event_manager.fire_event(
                PredictionEvents.prediction_done,
                json.loads(json.dumps(event_payload))
            )
            #
            return {'messages': [result]}, 200


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
