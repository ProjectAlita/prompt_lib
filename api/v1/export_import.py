from collections import defaultdict
from datetime import date
import json
from io import BytesIO
from itertools import chain

from flask import g, request, send_file
from pydantic import ValidationError
from pylon.core.tools import log

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ...models.pd.detail import PromptDetailModel
from ...models.pd.base import PromptBaseModel
from ...models.pd.collections import PromptIds
from tools import api_tools, db, auth, config as c

# from ...models.pd.example import ExampleModel
# from ...models.pd.export_import import PromptExport, PromptImport
# from ...models.pd.variable import VariableModel
# from ...models.prompts import Prompt
from ...models.all import Prompt
from ...models.pd.export_import import DialImportModel

from ...utils.create_utils import create_prompt
from ...utils.collections import create_collection
from ...utils.export_import_utils import prompts_export, prompts_export_to_dial, prompts_import_from_dial
from ...utils.constants import PROMPT_LIB_MODE


class ProjectAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api({
    #     "permissions": ["models.prompts.export_import.export"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def get(self, project_id: int, prompt_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).options(
                joinedload(Prompt.examples)
            ).options(
                joinedload(Prompt.variables)
            ).filter(
                Prompt.id == prompt_id,
            ).one_or_none()

            if not prompt:
                return {'error': f'Prompt with id: {prompt_id} not found'}, 400

            prompt.project_id = project_id
            result = PromptExport.from_orm(prompt).dict_flat(
                exclude_unset=True, by_alias=False, exclude={'integration_uid'}
            )

            result['examples'] = [
                ExampleModel.from_orm(i).dict(exclude={'id', 'prompt_id'})
                for i in prompt.examples
            ]
            result['variables'] = [
                VariableModel.from_orm(i).dict(exclude={'id', 'prompt_id'})
                for i in prompt.variables
            ]
            result['tags'] = [
                PromptTagModel.from_orm(i).dict(exclude={'id', 'prompt_id'})
                for i in prompt.tags
            ]
            if 'as_file' in request.args:
                file = BytesIO()
                data = json.dumps(result, ensure_ascii=False, indent=4)
                file.write(data.encode('utf-8'))
                file.seek(0)
                return send_file(file, download_name=f'{prompt.name}.json', as_attachment=False)
            return result, 200

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompts.export_import.import"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def post(self, project_id: int, **kwargs):
        try:
            integration_uid = request.json['integration_uid']
            if not integration_uid:
                raise ValueError
        except (KeyError, ValueError):
            return {'error': '"integration_uid" is required'}, 400

        examples = request.json.pop('examples', [])
        variables = request.json.pop('variables', [])
        tags = request.json.pop('tags', [])
        try:
            prompt_data = PromptImport.parse_obj(request.json)
        except Exception as e:
            log.critical(str(e))
            return {'error': str(e)}, 400

        prompt_dict = prompt_data.dict(exclude_unset=False, by_alias=True)
        log.info('settings parse result: %s', prompt_dict['model_settings'])

        if request.json.get('skip'):
            return {
                'examples': examples,
                'variables': variables,
                'tags': tags,
                **prompt_dict
            }, 200

        try:
            p = self.module.create(project_id=project_id, prompt=prompt_dict)
        except IntegrityError:
            return {'error': f'Prompt name \'{prompt_dict["name"]}\' already exists'}, 400

        for i in chain(examples, variables):
            i['prompt_id'] = p['id']
        self.module.create_examples_bulk(project_id=project_id, examples=examples)
        self.module.create_variables_bulk(project_id=project_id, variables=variables)
        self.module.update_tags(project_id=project_id, prompt_id=p['id'], tags=tags)
        return self.module.get_by_id(project_id, p['id']), 201


class PromptLibAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.export_import.export"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
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

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.export_import.import"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def post(self, project_id: int, **kwargs):
        created = []
        errors = []
        author_id = auth.current_user().get("id")

        if 'from_dial' in request.args:
            try:
                imported_data = DialImportModel.parse_obj(request.json)
            except Exception as e:
                log.critical(str(e))
                return {'error': str(e)}, 400

            folders = defaultdict(list)
            prompts_data = imported_data.dict(exclude_unset=True)

            with db.with_project_schema_session(project_id) as session:
                for prompt_data in prompts_data['prompts']:
                    prompt_data["author_id"] = author_id
                    prompt = prompts_import_from_dial(project_id, prompt_data, session)
                    result = PromptDetailModel.from_orm(prompt)
                    if folder_id := prompt_data['folderId']:
                        folders[folder_id].append(prompt.id)
                    created.append(json.loads(result.json()))
                session.commit()

            if prompts_data['folders']:
                created_collections = []
                for folder_data in prompts_data['folders']:
                    folder_data["owner_id"] = project_id
                    folder_data["author_id"] = author_id
                    folder_data["prompts"] = [
                        PromptIds(id=id_, owner_id=project_id)
                        for id_ in folders[folder_data['id']]
                        ]
                    result = create_collection(self.module.context, project_id, folder_data)
                    created_collections.append(result)
                created.append({'collections': created_collections})

        else:
            imported_data = dict(request.json)

            with db.with_project_schema_session(project_id) as session:
                for raw in imported_data.get('prompts'):
                    raw["owner_id"] = project_id
                    for version in raw.get("versions", []):
                        version["author_id"] = author_id
                    try:
                        prompt_data = PromptBaseModel.parse_obj(raw)
                    except ValidationError as e:
                        errors.append(e.errors())
                        continue

                    prompt = create_prompt(prompt_data, session)
                    session.flush()
                    result = PromptDetailModel.from_orm(prompt)
                    created.append(json.loads(result.json()))
                session.commit()

        return {'created': created, 'errors': errors}, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
