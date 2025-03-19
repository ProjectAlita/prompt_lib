from typing import Optional
from uuid import uuid4
from pathlib import Path

from flask import request, url_for
from pydantic import ValidationError
from tools import config as c, api_tools, auth, db

from ...models.all import PromptVersion
from ....promptlib_shared.utils.constants import PROMPT_LIB_MODE
from ....promptlib_shared.models.pd.icon_meta import UpdateIcon
from ...utils.prompt_icon_utils import change_prompt_icon


# routes/prompt_icon
FLASK_ROUTE_URL: str = 'prompt_lib.prompt_icon'
MAX_FILE_SIZE_KB: int = 512


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.upload_icon.get"],
        "recommended_roles": {
            c.DEFAULT_MODE: {"admin": True, "editor": False, "viewer": False},
        }})
    def get(self, **kwargs):
        return [
            {
                'name': i.name,
                'url': url_for(
                    FLASK_ROUTE_URL,
                    sub_path=f'{i.name}',
                    _external=True
                )
            } for i in self.module.prompt_icon_path.iterdir()
        ], 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.upload_icon.post"],
        "recommended_roles": {
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def post(self, project_id: int, prompt_version_id: Optional[int] = None, **kwargs):
        if 'file' not in request.files:
            return {'error': 'No file in request.files'}, 400

        file = request.files['file']

        # kB
        max_file_size = MAX_FILE_SIZE_KB * 1024

        # move the cursor to the end of the file
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > max_file_size:
            return {'error': f'File size exceeds {MAX_FILE_SIZE_KB} KB'}, 400

        final_width = int(request.form.get('width', 64))
        final_height = int(request.form.get('height', 64))
        file_name = f'{uuid4()}.png'
        file_path: Path = self.module.prompt_icon_path.joinpath(file_name)

        result = self.module.context.rpc_manager.call.social_save_image(
            file, file_path, FLASK_ROUTE_URL, final_width, final_height
        )
        if result['ok']:
            if prompt_version_id:
                change_prompt_icon(
                    project_id, prompt_version_id, self.module.prompt_icon_path, result['data']
                )
            return result['data'], 200
        else:
            return result['error'], 400

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.upload_icon.update"],
        "recommended_roles": {
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def put(self, project_id, prompt_version_id, **kwargs):
        raw = dict(request.json)
        try:
            update_input = UpdateIcon.parse_obj(raw)
        except ValidationError as e:
            return {'error': f'Validation error on item: {e}'}, 400

        with db.get_session(project_id) as session:
            version = session.query(PromptVersion).filter(
                PromptVersion.id == prompt_version_id
            ).first()
            if not version:
                return {'ok': False, 'msg': f'There is no such version id {prompt_version_id}'}

            if version.meta:
                version.meta['icon_meta'] = update_input.dict()
            else:
                version.meta = {'icon_meta': update_input.dict()}
            session.commit()

        return {'updated': True}, 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.upload_icon.delete"],
        "recommended_roles": {
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def delete(self, project_id, prompt_version_id, **kwargs):
        result = change_prompt_icon(
            project_id, prompt_version_id, self.module.prompt_icon_path, {}
        )
        if result['ok']:
            return result['data'], 200
        else:
            return result['error'], 400


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '',
        '<string:mode>/<string:file_name>',
        '<string:mode>/<int:project_id>',
        '<string:mode>/<int:project_id>/<int:prompt_version_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
