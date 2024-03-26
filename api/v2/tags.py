from flask import request

from pylon.core.tools import log
from tools import api_tools, auth, config as c
from ...utils.prompt_utils import get_prompt_tags
from ...utils.prompt_utils_legacy import get_all_tags, get_tags, update_tags

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.tags import list_tags

class ProjectAPI(api_tools.APIModeHandler):

    @auth.decorators.check_api({
        "permissions": ["models.prompts.tags.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id, prompt_id=None):
        if prompt_id:
            return {"demo": get_tags(project_id, prompt_id)}, 200
        return {"demo": get_all_tags(project_id)}, 200


class PromptLibAPI(api_tools.APIModeHandler):

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.tags.list"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id, prompt_id=None):
        if prompt_id:
            return {"demo": get_prompt_tags(project_id, prompt_id)}, 200
        return {"demo": list_tags(project_id, request.args)}, 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
        '<string:mode>/<int:project_id>/<int:prompt_id>',
        '<int:project_id>/<int:prompt_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
