import json
from io import BytesIO
from itertools import chain

from flask import request, send_file
from pylon.core.tools import log

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
# from ...models.pd.example import ExampleModel
# from ...models.pd.export_import import PromptExport, PromptImport
# from ...models.pd.variable import VariableModel
# from ...models.pd.tag import PromptTagModel
# from ...models.prompts import Prompt

from tools import api_tools, db, auth, config as c


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


class API(api_tools.APIBase):
    url_params = [
        '<int:project_id>/<int:prompt_id>',
        '<string:mode>/<int:project_id>/<int:prompt_id>',
        '<int:project_id>',
        '<string:mode>/<int:project_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
