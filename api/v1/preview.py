from flask import request
from tools import api_tools, auth, config as c


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.preview.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id: int, prompt_id: int):
        ignore_template_error = request.args.get('ignore_template_error', False)
        prompt_struct = self.module.prepare_prompt_struct(
            project_id, prompt_id, "",
            ignore_template_error=ignore_template_error
        )
        return prompt_struct, 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>/<int:prompt_id>',
        '<int:project_id>/<int:prompt_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
