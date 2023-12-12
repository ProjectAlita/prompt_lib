from ...utils.constants import PROMPT_LIB_MODE
from ...utils.publish_utils import Publishing
from tools import api_tools
from pylon.core.tools import log


class PromptLibAPI(api_tools.APIModeHandler):
    def post(self, project_id: int, version_id: int, **kwargs):
        try:
            result = Publishing(project_id, version_id).publish()
        except Exception as e:
            log.error(e)
            return {"ok": False, "error": str(e)}, 400
         
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
