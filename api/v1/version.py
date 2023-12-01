import json
from itertools import chain
from flask import request, g
from pydantic import ValidationError

from pylon.core.tools import log
from tools import api_tools, auth, config as c, db

from sqlalchemy.exc import IntegrityError
from ...models.all import PromptVersion
from ...models.pd.create import PromptVersionCreateModel
from ...models.pd.detail import PromptVersionDetailModel
from ...models.pd.update import PromptVersionUpdateModel
from ...utils.create_utils import create_version
from ...utils.prompt_utils import prompts_update_version
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.version.get"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def get(self, project_id: int, prompt_id: int, version_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompt_version = session.query(PromptVersion).filter(
                PromptVersion.id == version_id,
                PromptVersion.prompt_id == prompt_id
            ).first()
            if not prompt_version:
                return {'error': f'Prompt[{prompt_id}] version[{version_id}] not found'}, 400
            version_details = PromptVersionDetailModel.from_orm(prompt_version)
            version_details.author = auth.get_user(user_id=prompt_version.author_id)
            return json.loads(version_details.json()), 200

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.version.create"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def post(self, project_id: int, prompt_id: int, **kwargs):
        data = dict(request.json)
        data['author_id'] = g.auth.id
        data['prompt_id'] = prompt_id

        try:
            version_data = PromptVersionCreateModel.parse_obj(data)
        except ValidationError as e:
            return e.errors(), 400

        with db.with_project_schema_session(project_id) as session:
            prompt_version = create_version(version_data, session=session)
            try:
                session.commit()
            except IntegrityError:
                return {'error': f'Version with name {prompt_version.name} already exists'}, 400

            version_details = PromptVersionDetailModel.from_orm(prompt_version)
            version_details.author = auth.get_user(user_id=prompt_version.author_id)
            return json.loads(version_details.json()), 201

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.version.update"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def put(self, project_id: int, prompt_id: int, version_id: int = None, **kwargs):
        version_data = dict(request.json)
        version_data['author_id'] = g.auth.id
        version_data['prompt_id'] = prompt_id
        version_data['id'] = version_id
        try:
            version_data = PromptVersionUpdateModel.parse_obj(version_data)
        except ValidationError as e:
            return e.errors(), 400
        res = prompts_update_version(project_id, version_data)
        if not res['updated']:
            return res['msg'], 400
        return res['data'], 200

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.version.delete"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def delete(self, project_id: int, prompt_id: int, version_id: int = None):
        with db.with_project_schema_session(project_id) as session:
            if version := session.query(PromptVersion).get(version_id):
                if version.name == 'latest':
                    return {'error': 'You cannot delete latest prompt version'}, 400
                session.delete(version)
                session.commit()
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
