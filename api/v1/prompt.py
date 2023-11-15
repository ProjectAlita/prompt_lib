import json

from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from sqlalchemy.orm import joinedload
from ...models.all import Prompt, PromptVersion
from ...models.pd.detail import PromptDetailModel, PromptVersionDetailModel
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils_legacy import (
    prompts_delete_prompt,
    prompts_update_name,
    prompts_update_prompt
)

from tools import api_tools, auth, config as c, db


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompt.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id, prompt_id):
        version = request.args.get('version', 'latest').lower()
        prompt = self.module.get_by_id(project_id, prompt_id, version)
        if not prompt:
            return 'Prompt not found', 404
        return prompt

    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompt.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def put(self, project_id):
        try:
            prompt = prompts_update_prompt(project_id, dict(request.json))
            return prompt, 201
        except ValidationError as e:
            return e.errors(), 400

    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompt.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def patch(self, project_id, prompt_id):
        try:
            is_updated = prompts_update_name(project_id, prompt_id, dict(request.json))
            return '', 201 if is_updated else 404
        except ValidationError as e:
            return e.errors(), 400

    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompt.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def delete(self, project_id, prompt_id):
        version_name = request.args.get('version', 'latest').lower()
        is_deleted = prompts_delete_prompt(project_id, prompt_id, version_name)
        return '', 204 if is_deleted else 404


class PromptLibAPI(api_tools.APIModeHandler):
    def get(self, project_id: int, prompt_id: int, version_name: str = 'latest', **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompt_version = session.query(PromptVersion).options(
                joinedload(PromptVersion.prompt)
            ).options(
                joinedload(PromptVersion.variables)
            ).options(
                joinedload(PromptVersion.messages)
            ).filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.name == version_name
            ).first()
            if not prompt_version:
                return {'error': f'No prompt found with id \'{prompt_id}\' or no version \'{version_name}\''}, 400
            result = PromptDetailModel.from_orm(prompt_version.prompt)
            result.version_details = PromptVersionDetailModel.from_orm(prompt_version)
            result.version_details.author = auth.get_user(user_id=prompt_version.author_id)
            return json.loads(result.json()), 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>/<int:prompt_id>/<string:version_name>',
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI
    }
