from datetime import date
import json
from io import BytesIO

from flask import request, send_file

from pylon.core.tools import log

from tools import api_tools, db, auth, config as c

from ...utils.export_import_utils import collection_export
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.export"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, collection_id: int = None, **kwargs):
        to_dail = 'to_dial' in request.args
        try:
            result = collection_export(project_id, collection_id, to_dail)
        except Exception as e:
            return {"ok": False, "error": str(e)}, 404
        if 'as_file' in request.args:
            file = BytesIO()
            data = json.dumps(result, ensure_ascii=False, indent=4)
            file.write(data.encode('utf-8'))
            file.seek(0)
            return send_file(file, download_name=f'alita_collection_{date.today()}.json', as_attachment=False)
        return result, 200

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.export_import_collection.import"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    # def post(self, project_id: int, **kwargs):
    #     # created = []
    #     # errors = []
    #     created_prompts = []
    #     author_id = auth.current_user().get("id")
    #
    #     try:
    #         imported_data = CollectionImportModel.parse_obj(request.json)
    #     except Exception as e:
    #         log.critical(str(e))
    #         return {'error': str(e)}, 400
    #
    #     collection_data = imported_data.dict(exclude_unset=True)
    #     prompts = collection_data['prompts']
    #     collection_data["owner_id"] = project_id
    #     collection_data["author_id"] = author_id
    #
    #     if 'from_dial' in request.args:
    #         with db.with_project_schema_session(project_id) as session:
    #             for prompt_data in prompts:
    #                 prompt_data["author_id"] = author_id
    #                 prompt = prompts_import_from_dial(project_id, prompt_data, session)
    #                 result = PromptDetailModel.from_orm(prompt)
    #                 created_prompts.append(json.loads(result.json()))
    #             session.commit()
    #     else:
    #         with db.with_project_schema_session(project_id) as session:
    #             for raw in prompts:
    #                 raw["owner_id"] = project_id
    #                 for version in raw.get("versions", []):
    #                     version["author_id"] = author_id
    #                 try:
    #                     prompt_data = PromptBaseModel.parse_obj(raw)
    #                 except ValidationError as e:
    #                     return {'ok': False, "error": e}
    #                 prompt = create_prompt(prompt_data, session)
    #                 session.flush()
    #                 result = PromptDetailModel.from_orm(prompt)
    #                 created_prompts.append(json.loads(result.json()))
    #             session.commit()
    #
    #     collection_data["prompts"] = [
    #         PromptIds(id=prompt['id'], owner_id=project_id)
    #         for prompt in created_prompts
    #     ]
    #     new_collection = create_collection(project_id, collection_data)
    #     result = new_collection.to_json()
    #     result['prompts'] = created_prompts
    #     return result, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:collection_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
