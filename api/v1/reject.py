from ...utils.constants import PROMPT_LIB_MODE
from ...utils.publish_utils import set_public_version_status
from ...models.enums.all import PromptVersionStatus
from pylon.core.tools import log
from tools import api_tools, auth, config as c


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.reject.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def post(self, version_id: int, **kwargs):
        try:
            result = set_public_version_status(version_id, PromptVersionStatus.rejected)
        except Exception as e:
            log.error(e)
            return {"ok": False, "error": str(e)}, 400
        
        if not result['ok']:
            code = result.pop('error_code', 400)
            return result, code
        #
        prompt_version = result['result']
        return prompt_version, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:version_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
