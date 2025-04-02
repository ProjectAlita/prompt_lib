from pylon.core.tools import web, log

from pydantic import ValidationError

from tools import rpc_tools

from ..models.pd.import_wizard import IMPORT_MODEL_ENTITY_MAPPER
from ..utils.export_import_utils import (
    ENTITY_IMPORT_MAPPER, _wrap_import_error,
    _wrap_import_result
)


class RPC:
    @web.rpc('prompt_lib_import_wizard')
    def import_wizard(self, import_data: dict, project_id: int, author_id: int):
        rpc_call = rpc_tools.RpcMixin().rpc.call

        result, errors = {}, {}

        for key in ENTITY_IMPORT_MAPPER:
            result[key] = []
            errors[key] = []

        # applications, which requires to add toolkit separetly
        # when all initial app/ds/prompts/toolkits are imported
        postponed_applications = []
        # map exported import_uuid/import_version_uuid with real id's of saved entities
        postponed_id_mapper = {}

        # toolkits must be imported after all other entity types
        postponed_toolkits = {}
        for item_index, item in enumerate(import_data):
            has_postponed_toolkits = False
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

            if entity == 'toolkits':
                postponed_toolkits[item_index] = model.import_data
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
                    log.error(ex)
                    e = ["Import function has been failed"]
                if r:
                    if entity == 'agents':
                        has_postponed_toolkits = model.has_postponed_toolkits
                        if has_postponed_toolkits:
                            # result will be appended later when all toolkits will be added to apps
                            postponed_applications.append((item_index, model))
                    if not has_postponed_toolkits:
                        result[entity].append(_wrap_import_result(item_index, r))
                    postponed_id_mapper.update(model.map_postponed_ids(imported_entity=r))

                for er in e:
                    errors[entity].append(_wrap_import_error(item_index, er))

        # import all toolkits
        for item_index, toolkit in postponed_toolkits.items():
            try:
                r = rpc_call.applications_import_toolkit(
                    payload=toolkit.dict_import_uuid_resolved(postponed_id_mapper),
                    project_id=project_id,
                    author_id=author_id
                )
                result['toolkits'].append(_wrap_import_result(item_index, r))
                postponed_id_mapper.update(toolkit.map_postponed_ids(imported_entity=r))
            except Exception as ex:
                errors['toolkits'].append(_wrap_import_error(item_index, str(ex)))

        # link all toolkits with application versions, which are toolkit-incomplete
        application_ids_to_get_details = set()
        for item_index, postponed_application in postponed_applications:
            import_uuid = postponed_application.import_uuid
            try:
                application_id = postponed_id_mapper[import_uuid]
                application_ids_to_get_details.add((item_index, application_id))
            except KeyError:
                e = f"Agent with {import_uuid=} has not been imported, can not bind toolkits with it"
                errors['agents'].append(_wrap_import_error(item_index, e))
                continue

            for version in postponed_application.versions:
                import_version_uuid = version.import_version_uuid
                try:
                    application_version_id = postponed_id_mapper[import_version_uuid]
                except KeyError:
                    e = f"Agent version with {import_uuid=} {import_version_uuid=} has not been imported, can not bind toolkits with it"
                    errors['agents'].append(_wrap_import_error(item_index, e))
                    continue

                for postponed_toolkit_mapping in version.postponed_tools:
                    payload = {
                        "entity_version_id": application_version_id,
                        "entity_id": application_id,
                        "entity_type": "agent",
                        "has_relation": True
                    }
                    toolkit_import_uuid = postponed_toolkit_mapping.import_uuid
                    try:
                        toolkit_id = postponed_id_mapper[toolkit_import_uuid]
                    except KeyError:
                        e = f"Agent version with {import_uuid=} {import_version_uuid=} can not be bound with {toolkit_import_uuid=} cause the later was not imported"
                        errors['agents'].append(_wrap_import_error(item_index, e))
                        continue
                    try:
                        rpc_call.applications_toolkit_link(
                            project_id=project_id,
                            toolkit_id=toolkit_id,
                            payload=payload,
                        )
                    except Exception as ex:
                        log.error(ex)
                        e = f"Can not bind {toolkit_id=} with {application_id=} {application_version_id=}"
                        errors['agents'].append(_wrap_import_error(item_index, e))

        # Re-read details for correct result for all applications whith posponed tools
        for item_index, application_id in application_ids_to_get_details:
            try:
                r = rpc_call.applications_get_application_by_id(
                    project_id=project_id,
                    application_id=application_id,
                )
                result['agents'].append(_wrap_import_result(item_index, r))
            except Exception as ex:
                log.error(ex)
                e = f"Can not get detail for {application_id=}"
                errors['agents'].append(_wrap_import_error(item_index, e))

        return result, errors
