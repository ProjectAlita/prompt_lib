from ...utils.constants import PROMPT_LIB_MODE
from ...utils.publish_utils import unpublish
from tools import api_tools, auth
from pylon.core.tools import log


class PromptLibAPI(api_tools.APIModeHandler):
    def delete(self, version_id: int, **kwargs):
        try:
            current_user = auth.current_user().get("id")
            result = unpublish(current_user, version_id)
        except Exception as e:
            log.error(e)
            return {"ok": False, "error": str(e)}, 400
         
        if not result['ok']:
            code = result.pop('error_code', 400)
            return result, code
        #
        # prompt_version = result['prompt_version']
        return result, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:version_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
