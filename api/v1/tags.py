from flask import request

from pylon.core.tools import log
from tools import api_tools, auth, config as c


class ProjectAPI(api_tools.APIModeHandler):

    @auth.decorators.check_api({
        "permissions": ["models.prompts.tags.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id, prompt_id=None):
        if prompt_id:
            return self.module.get_tags(project_id, prompt_id), 200
        return self.module.get_all_tags(project_id), 200

    @auth.decorators.check_api({
        "permissions": ["models.prompts.tags.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def put(self, project_id, prompt_id):
        tags = request.json
        resp = self.module.update_tags(project_id, prompt_id, tags)
        return resp, 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
        '<string:mode>/<int:project_id>/<int:prompt_id>',
        '<int:project_id>/<int:prompt_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
