from collections import defaultdict
from datetime import date
import json
from io import BytesIO
from typing import Tuple

from flask import request, send_file
from pydantic import ValidationError
from pylon.core.tools import log

from ...models.all import Prompt
from ...models.pd.collections import PromptIds, CollectionModel
from tools import api_tools, db, auth, config as c

from ...models.pd.export_import import DialImportModel, PromptImportModel
from ...models.pd.prompt import PromptDetailModel
from ...models.pd.prompt_version import PromptVersionLatestCreateModel

from ...utils.create_utils import create_prompt, create_version
from ...utils.collections import create_collection
from ...utils.export_import_utils import prompts_export, prompts_export_to_dial
from ...utils.constants import PROMPT_LIB_MODE


def import_dial_prompts(data: dict, project_id: int, author_id: int) -> Tuple[dict, list]:
    parsed = DialImportModel.parse_obj(data)
    created = []
    created_collections = []
    errors = []
    folders = defaultdict(list)

    with db.with_project_schema_session(project_id) as session:
        for prompt_data in parsed.prompts:
            log.info(prompt_data)
            prompt = Prompt(
                name=prompt_data.name,
                description=prompt_data.description,
                owner_id=project_id
            )
            # log.info(prompt)
            model_settings = {'model': prompt_data.alita_model.dict()}
            if prompt_data.model:
                model_settings['max_tokens'] = prompt_data.model.maxLength
            ver = PromptVersionLatestCreateModel(
                name='latest',
                author_id=author_id,
                context=prompt_data.content,
                model_settings=model_settings
            )
            # log.info(ver.dict())
            create_version(ver, prompt=prompt, session=session)
            session.add(prompt)
            # session.flush()
            session.commit()
            session.refresh(prompt)
            result = PromptDetailModel.from_orm(prompt)
            if prompt_data.folderId:
                folders[prompt_data.folderId].append(prompt.id)
            created.append(json.loads(result.json()))
        session.commit()

    if parsed.folders:
        for folder_data in parsed.folders:
            collection = create_collection(project_id, folder_data.to_collection(
                project_id=project_id,
                author_id=author_id,
                prompt_ids=[
                    PromptIds(
                        id=i,
                        owner_id=project_id
                    ) for i in folders.get(folder_data.id, [])
                ]
            ))
            created_collections.append(collection.to_json())
    return {
        'prompts': created,
        'collections': created_collections
    }, errors


def import_alita_prompts(data: dict, project_id: int, author_id: int) -> Tuple[dict, list]:
    created = []
    created_collections = []
    errors = []
    folders = defaultdict(list)

    with db.with_project_schema_session(project_id) as session:
        for raw in data.get('prompts'):
            raw['owner_id'] = project_id
            for version in raw.get("versions", []):
                version["author_id"] = author_id
            try:
                prompt_data = PromptImportModel.parse_obj(raw)
            except ValidationError as e:
                errors.append(e.errors())
                continue
            prompt = create_prompt(prompt_data, session)
            created.append(prompt)
            session.commit()
            if prompt_data.collection_id:
                folders[prompt_data.collection_id].append(prompt.id)

        for folder_data in data.get('collections', []):
            coll = CollectionModel(
                name=folder_data.get("name"),
                owner_id=project_id,
                author_id=author_id,
                description=folder_data.get("description"),
                prompts=[]
            )
            if folder_data.get("id"):
                prompts = [
                    PromptIds(
                        id=i,
                        owner_id=project_id
                    ) for i in folders.get(folder_data['id'], [])
                ]
                coll.prompts = prompts

            collection = create_collection(project_id, coll)
            created_collections.append(collection.to_json())

        return {
            'prompts': [json.loads(PromptDetailModel.from_orm(i).json()) for i in created],
            'collections': created_collections
        }, errors


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.export"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, prompt_id: int = None, **kwargs):
        if 'to_dial' in request.args:
            result = prompts_export_to_dial(project_id, prompt_id)
        else:
            result = prompts_export(project_id, prompt_id)
        if 'as_file' in request.args:
            file = BytesIO()
            data = json.dumps(result, ensure_ascii=False, indent=4)
            file.write(data.encode('utf-8'))
            file.seek(0)
            return send_file(file, download_name=f'alita_prompts_{date.today()}.json', as_attachment=False)
        return result, 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.import"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, **kwargs):
        author_id = auth.current_user().get("id")
        is_dial_struct = 'folders' in request.json or 'from_dial' in request.args
        if is_dial_struct:
            try:
                created, errors = import_dial_prompts(dict(request.json), project_id, author_id)
            except ValidationError as e:
                return e.errors(), 400
            except Exception as e:
                log.exception('Import exception')
                return {'error': str(e)}, 400
        else:
            created, errors = import_alita_prompts(dict(request.json), project_id, author_id)
        return {'created': created, 'errors': errors}, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
