from ...utils.constants import PROMPT_LIB_MODE
from ...utils.publish_utils import Publishing
from tools import api_tools


class PromptLibAPI(api_tools.APIModeHandler):
    def post(self, project_id: int, version_id: int, **kwargs):
        result = Publishing(project_id, version_id).publish()
        
        if not result['ok']:
            code = result.pop('error_code', 400)
            return result, code
        #
        prompt_version = result['prompt_version']
        return prompt_version, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
        '<int:project_id>/<int:version_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
