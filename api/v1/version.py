import json
from flask import request
from pydantic import ValidationError

from pylon.core.tools import log
from tools import api_tools, auth, config as c, db

from sqlalchemy.exc import IntegrityError
from ...models.all import PromptVersion
from ...models.enums.events import PromptEvents
from ...models.pd.prompt_version import PromptVersionDetailModel, PromptVersionCreateModel, PromptVersionUpdateModel
from ...utils.create_utils import create_version
from ...utils.prompt_utils import prompts_update_version
from ...utils.publish_utils import fire_version_deleted_event
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.version.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, prompt_id: int, version_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompt_version = session.query(PromptVersion).filter(
                PromptVersion.id == version_id,
                PromptVersion.prompt_id == prompt_id
            ).first()
            if not prompt_version:
                return {'error': f'Prompt[{prompt_id}] version[{version_id}] not found'}, 400
            version_details = PromptVersionDetailModel.from_orm(prompt_version)
            return json.loads(version_details.json()), 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.version.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, prompt_id: int, **kwargs):
        data = dict(request.json)
        data['author_id'] = auth.current_user().get("id")
        data['prompt_id'] = prompt_id
        try:
            version_data = PromptVersionCreateModel.parse_obj(data)
        except ValidationError as e:
            return e.errors(), 400

        with db.with_project_schema_session(project_id) as session:
            try:
                prompt_version = create_version(version_data, session=session)
                session.commit()
            except IntegrityError:
                return {'error': f'Version with name {version_data.name} already exists'}, 400

            version_details = PromptVersionDetailModel.from_orm(prompt_version)
            self.module.context.event_manager.fire_event(
                PromptEvents.prompt_version_change, json.loads(version_details.json())
            )
            return json.loads(version_details.json()), 201

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.version.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def put(self, project_id: int, prompt_id: int, version_id: int = None, **kwargs):
        version_data = dict(request.json)
        version_data['author_id'] = auth.current_user().get("id")
        version_data['prompt_id'] = prompt_id
        version_data['id'] = version_id
        try:
            version_data = PromptVersionUpdateModel.parse_obj(version_data)
        except ValidationError as e:
            return e.errors(), 400
        res = prompts_update_version(project_id, version_data)
        if not res['updated']:
            return res['msg'], 400
        self.module.context.event_manager.fire_event(
            PromptEvents.prompt_change, res['data']
        )
        return res['data'], 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.version.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def delete(self, project_id: int, prompt_id: int, version_id: int = None):
        with db.with_project_schema_session(project_id) as session:
            if version := session.query(PromptVersion).get(version_id):
                version_data = version.to_json()
                prompt_data = version.prompt.to_json()
                if version.name == 'latest':
                    return {'error': 'You cannot delete latest prompt version'}, 400
                session.delete(version)
                session.commit()
                fire_version_deleted_event(project_id, version_data, prompt_data)
                return '', 204
            return '', 404


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>/<int:prompt_id>/<int:version_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
