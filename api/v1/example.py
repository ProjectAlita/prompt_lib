from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from tools import api_tools, auth, config as c


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.example.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def post(self, project_id):
        try:
            from_test_input = request.json.pop('from_test_input', False)
            prompt = self.module.create_example(project_id, request.json, from_test_input=from_test_input)
            return prompt, 201
        except ValidationError as e:
            return e.errors(), 400

    @auth.decorators.check_api({
        "permissions": ["models.prompts.example.put"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def put(self, project_id):
        try:
            prompt = self.module.update_example(project_id, request.json)
            return prompt, 201
        except ValidationError as e:
            return e.errors(), 400

    @auth.decorators.check_api({
        "permissions": ["models.prompts.example.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def delete(self, project_id, example_id):
        self.module.delete_example(project_id, example_id)
        return '', 204


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<string:mode>/<int:project_id>/<int:example_id>',
        '<int:project_id>',
        '<int:project_id>/<int:example_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
