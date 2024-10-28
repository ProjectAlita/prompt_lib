from datetime import date
import json
from io import BytesIO

from flask import request, send_file

from pylon.core.tools import log

from tools import api_tools, db, auth, config as c

from ...models.all import Collection
from ...models.pd.export_import import DialFolderExportModel
from ...utils.collections import group_by_project_id
from ...utils.export_import_utils import prompts_export_to_dial, prompts_export
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.collection_registry import ENTITY_REG


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.export"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, collection_id: int = None, **kwargs):
        forked = 'fork' in request.args
        result = {}
        with db.with_project_schema_session(project_id) as session:
            collection = session.query(Collection).get(collection_id)
            if not collection:
                raise Exception(f"Collection with id '{collection_id}' not found")

        for ent in ENTITY_REG:
            entities = ent.get_entities_field(collection)
            if not entities:
                continue
            result.update(
                ent.entity_export(group_by_project_id(entities), forked=forked)
            )

        if request.args.get('as_file', False):
            file = BytesIO()
            data = json.dumps(result, ensure_ascii=False, indent=4)
            file.write(data.encode('utf-8'))
            file.seek(0)
            return send_file(file, download_name=f'alita_collection_{date.today()}.json', as_attachment=False)
        return result, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:collection_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
