from datetime import date
import json
from io import BytesIO
from itertools import chain
from typing import List

from flask import g, request, send_file
from pylon.core.tools import log

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload


# from ...models.pd.example import ExampleModel
# from ...models.pd.export_import import PromptExport, PromptImport
# from ...models.pd.variable import VariableModel
# from ...models.prompts import Prompt
from ...utils.create_utils import create_version
from ...models.all import Prompt
from ...models.pd.base import PromptVersionBaseModel
from ...models.pd.dial import DialImportModel, DialModelImportModel, DialPromptImportModel

from tools import api_tools, db, auth, config as c
from ...utils.constants import PROMPT_LIB_MODE


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.export_import.export"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
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

    @auth.decorators.check_api({
        "permissions": ["models.prompts.export_import.import"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
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

    def get(self, project_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompts: List[Prompt] = session.query(Prompt).options(
                joinedload(Prompt.versions)).all()

            prompts_to_export = []
            for prompt in prompts:
                latest_version = prompt.get_latest_version()
                export_data = {
                    'content': latest_version.context or '',
                    **prompt.to_json()
                }
                if latest_version.model_settings:
                    export_data['model'] = DialModelImportModel(
                        id=latest_version.model_settings.get('model', {}).get('name', '')
                        )
                prompts_to_export.append(DialPromptImportModel(**export_data))

            result = DialImportModel(prompts=prompts_to_export, folders=[])
            result = result.dict()

            if 'as_file' in request.args:
                file = BytesIO()
                data = json.dumps(result, ensure_ascii=False, indent=4)
                file.write(data.encode('utf-8'))
                file.seek(0)
                return send_file(file, download_name=f'alita_prompts_{date.today()}.json', as_attachment=False)
            return result, 200

    def post(self, project_id: int, **kwargs):
        try:
            prompts_data = DialImportModel.parse_obj(request.json)
        except Exception as e:
            log.critical(str(e))
            return {'error': str(e)}, 400

        prompts_dict = prompts_data.dict(exclude_unset=True)
        log.info('settings parse result: %s', prompts_dict)

        with db.with_project_schema_session(project_id) as session:
            for prompt_dict in prompts_dict['prompts']:
                prompt = Prompt(
                    name=prompt_dict['name'],
                    description=prompt_dict.get('description'),
                    owner_id=project_id
                )
                ver = PromptVersionBaseModel(
                    name='latest',
                    author_id=g.auth.id,
                    context=prompt_dict['content'],
                    type='chat'
                )
                create_version(ver, prompt=prompt, session=session)
                session.add(prompt)
            session.commit()

        return '', 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
