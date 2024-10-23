from typing import Tuple

from flask import request, send_file
from pydantic import ValidationError
from sqlalchemy.exc import ProgrammingError
from tools import api_tools, db, auth, config as c

from ...models.all import Prompt
from ...models.pd.fork import ForkPromptInput
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.import"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, **kwargs) -> Tuple[dict, int]:
        fork_data = request.json
        author_id = auth.current_user().get("id")

        try:
            fork_input = ForkPromptInput.parse_obj(fork_data)
        except ValidationError as e:
            return {'result': None, 'errors': [f'Validation error on item: {e}']}, 400

        results, errors = [], []

        for fork_input_prompt in fork_input.prompts:
            try:
                with db.with_project_schema_session(fork_input_prompt.owner_id) as session:
                    original_prompt = session.query(Prompt).filter(Prompt.id == fork_input_prompt.id).first()
                    if not original_prompt:
                        errors.append(f'Prompt with id {fork_input_prompt.id} does not exist')
                    else:
                        new_prompt = original_prompt.to_json()
                        new_prompt['versions'] = []
                        input_prompt_model_settings = {version.id: version.model_settings.dict()
                                                       for version in fork_input_prompt.versions}

                        for original_prompt_version in original_prompt.versions:
                            if original_prompt_version.id not in input_prompt_model_settings.keys():
                                continue

                            new_prompt_version = original_prompt_version.to_json()
                            new_prompt_version.pop('id')

                            new_prompt_version['tags'] = []
                            for i in original_prompt_version.tags:
                                new_prompt_version['tags'].append(i.to_json())

                            new_prompt_version['model_settings'] = input_prompt_model_settings.get(
                                original_prompt_version.id
                            )

                            meta = new_prompt_version.get('meta', {}) or {}

                            if 'parent_entity_id' not in meta:
                                shared_id = new_prompt_version.get('shared_id')
                                shared_owner_id = new_prompt_version.get('shared_owner_id')

                                if shared_id and shared_owner_id:
                                    parent_entity_id = shared_id
                                    parent_project_id = shared_owner_id
                                else:
                                    parent_entity_id = fork_input_prompt.id
                                    parent_project_id = fork_input_prompt.owner_id

                                meta.update({
                                    'parent_entity_id': parent_entity_id,
                                    'parent_project_id': parent_project_id
                                })
                                new_prompt_version['meta'] = meta
                            new_prompt['versions'].append(new_prompt_version)

                        if not new_prompt['versions']:
                            return {'result': None, 'errors': [
                                f'No versions were found for the prompt: {fork_input_prompt.id}'
                            ]}, 400
                        new_prompt.pop('id')
                        result, error = self.module.context.rpc_manager.call.prompt_lib_import_prompt(
                            new_prompt, project_id, author_id
                        )
                        results.append(result)
                        results.extend(error)
            except ProgrammingError:
                return {'result': None, 'errors': [
                    f'The project with id {fork_input_prompt.owner_id} does not exist'
                ]}, 404
        status_code: int = 201 if not errors else 400
        return {'result': results, 'errors': errors}, status_code


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
