import uuid
from itertools import chain
from typing import Tuple

from flask import request, send_file
from pydantic import ValidationError
from sqlalchemy.exc import ProgrammingError
from tools import api_tools, rpc_tools, db, auth, config as c

from ...models.all import Prompt
from ...models.pd.fork import ForkPromptInput
from ...utils.constants import PROMPT_LIB_MODE
from ....promptlib_shared.utils.permissions import ProjectPermissionChecker


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.fork.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, **kwargs) -> Tuple[dict, int]:
        fork_data = request.json
        author_id = auth.current_user().get("id")
        results, errors = {'prompts': []}, {'prompts': []}
        already_exists = {'prompts': []}

        try:
            fork_input = ForkPromptInput.parse_obj(fork_data)
        except ValidationError as e:
            errors['prompts'].append(f'Validation error on item: {e}')
            return {'result': results, 'errors': errors}, 400

        new_idxs = []

        for idx, fork_input_prompt in enumerate(fork_input.prompts):
            permission_checker = ProjectPermissionChecker(fork_input_prompt.owner_id)
            check_owner_permission, status_code = permission_checker.check_permissions(
                ["models.applications.fork.post"]
            )
            if status_code != 200:
                return check_owner_permission, status_code

            parent_entity_id = fork_input_prompt.id
            parent_project_id = fork_input_prompt.owner_id
            for fork_input_prompt_version in fork_input_prompt.versions:
                if fork_input_prompt_version.meta:
                    parent_entity_id = fork_input_prompt_version.meta.get('parent_entity_id', fork_input_prompt.id)
                    parent_project_id = fork_input_prompt_version.meta.get('parent_project_id', fork_input_prompt.owner_id)

            forked_prompt_id, forked_prompt_version_id = self.module.context.rpc_manager.call.prompt_lib_find_existing_fork(
                target_project_id=project_id,
                parent_entity_id=parent_entity_id,
                parent_project_id=parent_project_id
            )
            if forked_prompt_id and forked_prompt_version_id:
                forked_prompt_details = rpc_tools.RpcMixin().rpc.call.prompt_lib_get_by_id(
                    project_id, forked_prompt_id
                )
                forked_prompt_details['import_uuid'] = fork_input_prompt.import_uuid
                forked_prompt_details['index'] = idx
                already_exists['prompts'].append(forked_prompt_details)
                continue
            try:
                with db.with_project_schema_session(fork_input_prompt.owner_id) as session:
                    original_prompt = session.query(Prompt).filter(Prompt.id == fork_input_prompt.id).first()
                    if not original_prompt:
                        errors['prompts'].append(f'Prompt with id {fork_input_prompt.id} does not exist')
                        return {'result': results, 'errors': errors}, 400
                    else:
                        new_prompt = original_prompt.to_json()
                        new_prompt['versions'] = []
                        input_prompt_model_settings = {version.id: version.model_settings.dict()
                                                       for version in fork_input_prompt.versions}

                        for original_prompt_version in original_prompt.versions:
                            if original_prompt_version.id not in input_prompt_model_settings.keys():
                                continue

                            new_prompt_version = original_prompt_version.to_json()
                            hash_ = hash((new_prompt_version['id'], new_prompt_version['author_id'], new_prompt_version['name']))
                            new_prompt_version['import_version_uuid'] = str(uuid.UUID(int=abs(hash_)))
                            new_prompt_version.pop('id')

                            new_prompt_version['tags'] = []
                            for tag in original_prompt_version.tags:
                                new_prompt_version['tags'].append(tag.to_json())

                            new_prompt_version['variables'] = []
                            for var in original_prompt_version.variables:
                                new_prompt_version['variables'].append(var.to_json())

                            new_prompt_version['messages'] = [msg.to_json() for msg in original_prompt_version.messages]

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
                                    'parent_entity_version_id': original_prompt_version.id,
                                    'parent_project_id': parent_project_id,
                                    'parent_author_id': original_prompt_version.author_id,
                                })
                                new_prompt_version['meta'] = meta
                            new_prompt['versions'].append(new_prompt_version)

                        if not new_prompt['versions']:
                            return {'result': results, 'errors': [
                                f'No versions were found for the prompt: {fork_input_prompt.id}'
                            ]}, 400

                        new_prompt['entity'] = 'prompts'
                        hash_ = hash((new_prompt['id'], new_prompt['owner_id'], new_prompt['name']))
                        new_prompt['import_uuid'] = str(uuid.UUID(int=abs(hash_)))
                        new_prompt.pop('id')
                        new_prompt['index'] = idx
                        new_idxs.append(idx)
                        results['prompts'].append(new_prompt)
            except ProgrammingError:
                errors['prompts'].append({
                    'index': idx,
                    'msg': f'The project with id {fork_input_prompt.owner_id} does not exist'
                })
                return {'result': results, 'errors': errors}, 404

        if results['prompts']:
            import_wizard_result, errors = self.module.context.rpc_manager.call.prompt_lib_import_wizard(
                results['prompts'], project_id, author_id
            )
        else:
            import_wizard_result = results

        has_results = any(import_wizard_result[key] for key in import_wizard_result if import_wizard_result[key])
        has_errors = any(errors[key] for key in errors if errors[key])

        if not has_errors and has_results:
            status_code = 201
        elif has_errors and has_results:
            status_code = 207
        elif not has_errors and not has_errors:
            status_code = 200
        else:
            status_code = 400

        for entity in import_wizard_result:
            for i in chain(import_wizard_result[entity], errors[entity]):
                i['index'] = new_idxs[i['index']]

        return {'result': import_wizard_result, 'already_exists': already_exists, 'errors': errors}, status_code


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
