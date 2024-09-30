from flask import request, send_file

from tools import api_tools, db, auth, config as c

from pydantic import ValidationError
from ...models.all import Prompt
from ...models.pd.fork import ForkPromptBase

from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.import"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, prompt_id: int, **kwargs):
        fork_data = request.json
        author_id = auth.current_user().get("id")

        try:
            model = ForkPromptBase.parse_obj(fork_data)
        except ValidationError as e:
            return f'Validation error on item: {e}', 400

        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).filter(Prompt.id == prompt_id).first()
            prompt_with_versions = prompt.to_json()
            prompt_with_versions['versions'] = []
            for v in prompt.versions:
                if v.id not in model.versions:
                    continue
                # TODO parse model settings from payload
                v_data = v.to_json()
                v_data['tags'] = []
                for i in v.tags:
                    v_data['tags'].append(i.to_json())

                # skip if parent_entity_id in meta
                if 'parent_entity_id' not in v_data.get('meta', {}):
                    shared_id = v_data.get('shared_id')
                    shared_owner_id = v_data.get('shared_owner_id')

                    if shared_id and shared_owner_id:
                        parent_entity_id = shared_id
                        parent_project_id = shared_owner_id
                    else:
                        parent_entity_id = prompt_id
                        parent_project_id = project_id

                    meta = v_data.get('meta', {})
                    meta.update({
                        'parent_entity_id': parent_entity_id,
                        'parent_project_id': parent_project_id
                    })
                    v_data['meta'] = meta

                prompt_with_versions['versions'].append(v_data)

        result, errors = self.module.context.rpc_manager.call.prompt_lib_import_prompt(
            prompt_with_versions, model.target_project_id, author_id
        )
        # TODO add if in "publish prompt" to create new copy in fork original prompt
        return {'result': result, 'errors': errors}, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
