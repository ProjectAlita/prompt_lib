from ...utils.constants import PROMPT_LIB_MODE
from ...utils.publish_utils import Publishing
from pylon.core.tools import log
from tools import api_tools, auth, config as c

# class

class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.publish.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, version_id: int, **kwargs):
        # publish_model =
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
