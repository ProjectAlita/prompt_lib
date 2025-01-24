from pylon.core.tools import web

from pydantic.v1 import ValidationError
from pydantic.v1.utils import deep_update

from tools import rpc_tools

from ..models.pd.import_wizard import IMPORT_MODEL_ENTITY_MAPPER
from ..utils.export_import_utils import (
    ENTITY_IMPORT_MAPPER, _wrap_import_error,
    _postponed_app_tools_import, _wrap_import_result
)


class RPC:
    @web.rpc('prompt_lib_import_wizard')
    def import_wizard(self, import_data: dict, project_id: int, author_id: int):
        rpc_call = rpc_tools.RpcMixin().rpc.call

        result, errors = {}, {}

        for key in ENTITY_IMPORT_MAPPER:
            result[key] = []
            errors[key] = []

        # tools deleted from initial application importing
        # to add separetly, when all initial app/ds/prompts are imported
        postponed_application_tools = []
        # map exported import_uuid/import_version_uuid with real id's of saved entities
        postponed_id_mapper = {}
        for item_index, item in enumerate(import_data):
            postponed_tools = []
            entity = item['entity']
            entity_model = IMPORT_MODEL_ENTITY_MAPPER.get(entity)
            if entity_model:
                try:
                    model = entity_model.parse_obj(item)
                except ValidationError as e:
                    errors[entity].append(_wrap_import_error(item_index, f'Validation error: {e}'))
                    continue
            else:
                errors[entity].append(_wrap_import_error(item_index, f'No such {entity} in import entity mapper'))
                continue

            model_data = model.dict()

            rpc_func = ENTITY_IMPORT_MAPPER.get(entity)
            if rpc_func:
                r = e = None
                try:
                    r, e = getattr(rpc_call, rpc_func)(
                        model_data, project_id, author_id
                    )
                except Exception as ex:
                    e = [str(ex)]
                if r:
                    if entity == 'agents':
                        postponed_tools = model.postponed_tools
                        postponed_application_tools.append((item_index, postponed_tools))
                    # result will be appended later when all tools will be added to agent
                    if not postponed_tools:
                        result[entity].append(_wrap_import_result(item_index, r))
                    postponed_id_mapper = deep_update(
                        postponed_id_mapper,
                        model.map_postponed_ids(imported_entity=r)
                    )

                for er in e:
                    errors[entity].append(_wrap_import_error(item_index, er))

        if postponed_application_tools:
            tool_results, tool_errors = _postponed_app_tools_import(
                postponed_application_tools,
                postponed_id_mapper,
                project_id
            )
            result['agents'].extend(tool_results)
            errors['agents'].extend(tool_errors)

        return result, errors
