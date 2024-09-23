from flask import request, send_file

from tools import api_tools, db, auth, config as c

from pydantic import ValidationError

from ...models.pd.import_wizard import IMPORT_MODEL_ENTITY_MAPPER
from ...utils.constants import PROMPT_LIB_MODE


ENTITY_IMPORT_MAPPER = {
    'prompts': 'prompt_lib_import_prompt',
    'datasources': 'datasources_import_datasource',
    'agents': 'applications_import_application',
}


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.export_import.import"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, project_id: int, **kwargs):
        import_data = request.json
        author_id = auth.current_user().get("id")
        result, errors = [], []

        for item in import_data:
            entity = item['entity']
            entity_model = IMPORT_MODEL_ENTITY_MAPPER.get(entity)
            if entity_model:
                try:
                    model = entity_model.parse_obj(item).dict()
                except ValidationError as e:
                    return f'Validation error on item {entity}: {e}', 400
            else:
                return f'No such {entity} in import entity mapper', 400

            rpc_func = ENTITY_IMPORT_MAPPER.get(entity)
            if rpc_func:
                r, e = getattr(self.module.context.rpc_manager.call, rpc_func)(
                    model, project_id, author_id
                )
                result.append(r)
                errors.extend(e)

        return {'result': result, 'errors': errors}, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
