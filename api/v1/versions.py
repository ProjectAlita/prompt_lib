from itertools import chain
from flask import request

from pylon.core.tools import log
from tools import api_tools, auth, config as c, db

from ...models.all import PromptVersion


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.versions.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id, version_name: str, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompts = session.query(PromptVersion).filter(
                PromptVersion.name == version_name
            ).all()
            return [prompt.to_json() for prompt in prompts]

    @auth.decorators.check_api({
        "permissions": ["models.prompts.versions.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def post(self, project_id, **kwargs):
        prompt_data = self.module.get_by_id(project_id, request.json['prompt_id'])
        prompt_data.pop('test_input')
        prompt_data.update({'version': request.json['version']})
        prompt = self.module.create(project_id, prompt_data)
        for i in chain(prompt_data['variables'], prompt_data['examples']):
            i['prompt_id'] = prompt['id']
        self.module.create_variables_bulk(project_id, prompt_data['variables'])
        self.module.create_examples_bulk(project_id, prompt_data['examples'])
        self.module.update_tags(project_id, prompt['id'], prompt_data['tags'])
        return prompt, 201


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
        '<string:mode>/<int:project_id>/<string:version_name>',
        '<int:project_id>/<string:version_name>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
