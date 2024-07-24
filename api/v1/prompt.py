import json

from flask import request
from pydantic import ValidationError
from pylon.core.tools import log


from ...models.all import Prompt
from ...models.enums.events import PromptEvents
from ...models.pd.prompt import PromptDetailModel
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils import get_prompt_details
from ...utils.prompt_utils_legacy import (
    prompts_update_name,
    prompts_update_prompt,
    prompts_delete_prompt
)
from ...utils.publish_utils import is_public_project

from tools import api_tools, auth, config as c, db


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompt.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
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
    @api_tools.endpoint_metrics
    def put(self, project_id: int):
        try:
            prompt = prompts_update_prompt(project_id, dict(request.json))
            return prompt, 200
        except ValidationError as e:
            return e.errors(), 400

    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompt.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
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
    @api_tools.endpoint_metrics
    def delete(self, project_id, prompt_id):
        version_name = request.args.get('version', 'latest').lower()
        is_deleted = prompts_delete_prompt(project_id, prompt_id, version_name)
        return '', 204 if is_deleted else 404


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.prompt.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, prompt_id: int, version_name: str = 'latest', **kwargs):
        result = get_prompt_details(project_id, prompt_id, version_name)
        if not result['ok']:
            return {'error': result['msg']}, 400
        return json.loads(result['data']), 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.prompt.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def delete(self, project_id: int, prompt_id: int, **kwargs):
        with db.get_session(project_id) as session:
            is_public, public_id = False, None
            try:
                is_public, public_id = is_public_project(project_id)
                if is_public:
                    return {"ok": False, "error": "Deleting from public project is prohibited"}, 400
            except Exception:
                log.warning('Public project is not set so any prompt can be deleted')
                pass

            if prompt := session.query(Prompt).get(prompt_id):
                prompt_details = PromptDetailModel.from_orm(prompt)
                session.delete(prompt)
                session.commit()
                # fire_prompt_deleted_event(project_id, prompt)

                payload = {
                    'prompt_data': prompt_details.dict(),
                    'public_id': public_id,
                    'is_public': is_public
                }

                self.module.context.event_manager.fire_event(
                    PromptEvents.prompt_deleted, payload
                )
                return '', 204
            return {"ok": False, "error": "Prompt is not found"}, 404


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
