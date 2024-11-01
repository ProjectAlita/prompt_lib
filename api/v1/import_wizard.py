from typing import List

from flask import request

from tools import api_tools, auth, config as c, rpc_tools

from pydantic import ValidationError
from pydantic.utils import deep_update

from ...models.pd.import_wizard import ApplicationImportCompoundTool, IMPORT_MODEL_ENTITY_MAPPER
from ...utils.constants import PROMPT_LIB_MODE


ENTITY_IMPORT_MAPPER = {
    'prompts': 'prompt_lib_import_prompt',
    'datasources': 'datasources_import_datasource',
    'agents': 'applications_import_application',
}


def postponed_app_tools_import(postponed_application_tools: List[ApplicationImportCompoundTool], postponed_id_mapper, project_id):
    rpc_call = rpc_tools.RpcMixin().rpc.call

    errors = []
    results = {}
    for tool in postponed_application_tools:
        app_ver_id, payload = tool.generate_create_payload(postponed_id_mapper)
        result = rpc_call.applications_add_application_tool(
            payload,
            project_id,
            app_ver_id,
            return_details=True
        )
        if not result['ok']:
            errors.append(result['error'])
        else:
            # the most recent tools update overwrites result with the most actual data
            results[app_ver_id] = result['details']

    return results.values(), errors


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
        result, errors = {}, {}

        for key in ENTITY_IMPORT_MAPPER:
            result[key] = []
            errors[key] = []

        # tools deleted from initial application importing
        # to add separetly, when all initial app/ds/prompts are imported
        postponed_application_tools = []
        # map exported import_uuid/import_version_uuid with real id's of saved entities
        postponed_id_mapper = {}
        for item in import_data:
            postponed_tools = []
            entity = item['entity']
            entity_model = IMPORT_MODEL_ENTITY_MAPPER.get(entity)
            if entity_model:
                try:
                    model = entity_model.parse_obj(item)
                except ValidationError as e:
                    return {'errors': {entity: [f'Validation error on item {entity}: {e}']}}, 400
            else:
                return {'errors': {entity: [f'No such {entity} in import entity mapper']}}, 400

            if entity == 'agents':
                postponed_tools = model.postponed_tools
                postponed_application_tools.extend(postponed_tools)

            model_data = model.dict()

            rpc_func = ENTITY_IMPORT_MAPPER.get(entity)
            if rpc_func:
                r, e = getattr(self.module.context.rpc_manager.call, rpc_func)(
                    model_data, project_id, author_id
                )
                if r:
                    # result will be appended later when all tools will be added to agent
                    if not postponed_tools:
                        result[entity].append(r)
                    postponed_id_mapper = deep_update(
                        postponed_id_mapper,
                        model.map_postponed_ids(imported_entity=r)
                    )
                errors[entity].extend(e)

        if postponed_application_tools:
            tool_results, tool_errors = postponed_app_tools_import(
                postponed_application_tools,
                postponed_id_mapper,
                project_id
            )
            result['agents'].extend(tool_results)
            errors['agents'].extend(tool_errors)

        has_results = any(result[key] for key in result if result[key])
        has_errors = any(errors[key] for key in errors if errors[key])

        if not has_errors and has_results:
            status_code = 201
        elif has_errors and has_results:
            status_code = 207
        else:
            status_code = 400

        return {'result': result, 'errors': errors}, status_code


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
