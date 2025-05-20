from itertools import chain
from flask import request

from pylon.core.tools import log
from tools import api_tools, auth, config as c, db

from ...models.pd.v1_structure import VersionV1Model
from ...models.all import Prompt


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.versions.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id, prompt_id: str, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).get(prompt_id)
            return [VersionV1Model(**version.to_json()).dict() for version in prompt.versions]

    @auth.decorators.check_api({
        "permissions": ["models.prompts.versions.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
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
    url_params = api_tools.with_modes([
        '<int:project_id>',
        '<int:project_id>/<string:prompt_id>',  # changed from prompt_name in legacy
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
