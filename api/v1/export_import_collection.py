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


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.export"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, collection_id: int = None, **kwargs):
        # TODO: rewrite to be something like:
        #result = {}
        #for ent in ENTITY_REG:
        #    entities = ent.get_entities_fields(collection)
        #    if not entities:
        #        continue
        #    result_entities = []
        #    for project_id, entities in group_by_project_id(entities).items():
        #        for entity_id in entities:
        #            result_entities.append(ent.entity_export_rpc(project_id, entity_id))
        #    result[ent.entity_name] = result_entities
        to_dial = request.args.get('to_dial', False)
        with db.with_project_schema_session(project_id) as session:
            collection = session.query(Collection).get(collection_id)
            if not collection:
                raise Exception(f"Collection with id '{collection_id}' not found")
            grouped_prompts = group_by_project_id(collection.prompts)
            result_prompts = []
            for project_id, prompts in grouped_prompts.items():
                with db.with_project_schema_session(project_id) as session2:
                    for prompt_id in prompts:
                        if to_dial:
                            result = prompts_export_to_dial(project_id, prompt_id, session2)
                        else:
                            result = prompts_export(project_id, prompt_id, session2)
                            del result['collections']
                        result_prompts.extend(result['prompts'])

            result = {"prompts": result_prompts}
            if to_dial:
                folder_id = f'alita_{project_id}_{collection_id}'
                folder = DialFolderExportModel(
                    id=folder_id,
                    name=collection.name,
                    type='prompt'
                )
                for i in result['prompts']:
                    i['folderId'] = folder_id
                result["folders"] = [folder.dict()]
            else:
                folder = {"name": collection.name, "description": collection.description, 'id': collection_id}
                for i in result['prompts']:
                    i['collection_id'] = collection_id
                result["collections"] = [folder]
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
