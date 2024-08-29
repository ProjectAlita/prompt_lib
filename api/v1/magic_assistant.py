from flask import request
from pydantic import ValidationError
from tools import api_tools, auth, VaultClient, serialize, config as c
from pylon.core.tools import log

from ...models.pd.magic_assistant import MagicAssistantPredict, MagicAssistantResponse
from ...utils.conversation import prepare_payload, prepare_conversation, CustomTemplateError
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.generate_prompt_utils import get_generated_prompt_content
from ...utils.publish_utils import get_public_project_id

try:
    from langchain_openai import AzureChatOpenAI
except:
    from langchain.chat_models import AzureChatOpenAI


class PromptLibAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api({
    #     "permissions": ["models.prompts.magic_assistant.post"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def post(self, project_id: int, **kwargs):
        payload = dict(request.json)

        try:
            data = MagicAssistantPredict.parse_obj(payload)
        except Exception as e:
            return {'error': str(e)}, 400

        private_secrets = VaultClient(project_id).get_secrets()
        magic_assistant_prompt_version_id = private_secrets.get('magic_assistant_version_id')

        if not magic_assistant_prompt_version_id:
            project_id = get_public_project_id()
            admin_secrets = VaultClient(project_id).get_all_secrets()
            magic_assistant_prompt_version_id = admin_secrets.get('magic_assistant_version_id')
            if not magic_assistant_prompt_version_id:
                return {'error': 'No magic_assistant_version_id were found'}, 400

        user_name = auth.current_user().get('name')

        raw_data = {
            **data.dict(),
            'project_id': project_id,
            'prompt_version_id': int(magic_assistant_prompt_version_id),
            'user_name': user_name,
        }

        try:
            payload = prepare_payload(data=raw_data)
        except ValidationError as e:
            return {'error': str(e)}, 400

        try:
            conversation = prepare_conversation(payload=payload)
        except CustomTemplateError as e:
            return {'error': str(e)}, 400
        except Exception as e:
            return {'error': str(e)}, 400

        result = get_generated_prompt_content(payload, conversation)

        if not result:
            return {'error': 'No result from AI provider'}, 400

        try:
            response = MagicAssistantResponse.parse_obj(result)
            log.debug(f'{result}=')
        except ValidationError:
            log.warning('LLM did not return required values, second attempt...')
            regenerated_result = get_generated_prompt_content(payload, conversation)
            log.debug(f'{regenerated_result}=')
            response = MagicAssistantResponse.create_from_dict(regenerated_result)

        return serialize(response.dict()), 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
    ]

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
