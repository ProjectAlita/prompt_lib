import copy
from typing import List
from sqlalchemy.orm import joinedload

from tools import db, rpc_tools

from ..models.all import Prompt, PromptVersion
from ..models.pd.export_import import (
    PromptExportModel, DialExportModel,
    DialPromptExportModel, DialModelExportModel, PromptForkModel,
)
from ..models.pd.import_wizard import ApplicationImportCompoundTool
from ..models.pd.model_settings import ModelSettingsBaseModel


ENTITY_IMPORT_MAPPER = {
    'prompts': 'prompt_lib_import_prompt',
    'datasources': 'datasources_import_datasource',
    'agents': 'applications_import_application',
}


def prompts_export_to_dial(project_id: int, prompt_id: int = None, session=None) -> dict:
    if session is None:
        session = db.get_project_schema_session(project_id)

    filters = [Prompt.id == prompt_id] if prompt_id else []
    prompts: List[Prompt] = session.query(Prompt).filter(*filters).options(
        joinedload(Prompt.versions)).all()

    prompts_to_export = []
    for prompt in prompts:
        for version in prompt.versions:
            export_data = DialPromptExportModel(
                id=prompt.id,
                name=prompt.name,
                description=prompt.description,
                content=version.context,
            )
            if version.model_settings:
                parsed = ModelSettingsBaseModel.parse_obj(version.model_settings)
                export_data.model = DialModelExportModel(
                    id=parsed.model.model_name,
                    maxLength=parsed.max_tokens,
                )
            prompts_to_export.append(export_data.dict())
    result = DialExportModel(prompts=prompts_to_export, folders=[])
    session.close()
    return result.dict()


def prompts_export(project_id: int, prompt_id: int = None, session=None, forked=False) -> dict:
    if session is None:
        session = db.get_project_schema_session(project_id)

    filters = [Prompt.id == prompt_id] if prompt_id else []
    query = (
        session.query(Prompt)
        .filter(*filters)
        .options(
            joinedload(Prompt.versions)
            .options(
                joinedload(PromptVersion.variables),
                joinedload(PromptVersion.messages),
                joinedload(PromptVersion.tags)
            )
        )
    )
    prompts: List[Prompt] = query.all()
    prompts_to_export = []
    for prompt in prompts:
        if forked:
            prompt_data = PromptForkModel.from_orm(prompt)
        else:
            prompt_data = PromptExportModel.from_orm(prompt)
        prompts_to_export.append(prompt_data.dict())

    session.close()
    return {'prompts': prompts_to_export}


def _wrap_import_error(ind, msg):
    return {
        "index": ind,
        "msg": msg
    }


def _wrap_import_result(ind, result):
    result['index'] = ind
    return result


def _recalculate_failed_good_results(incomplete_apps, already_connected_info):
    failed = copy.copy(incomplete_apps)
    redo = False

    good = []
    for app_id, connected_app_id, original_entity_index in already_connected_info:
        if connected_app_id in failed:
            if app_id not in failed:
                failed[app_id] = original_entity_index
                redo = True
        else:
            good.append((app_id, connected_app_id, original_entity_index))

    if redo:
        failed_rec, good = _recalculate_failed_good_results(failed, good)
        failed.update(failed_rec)

    return failed, good


def _postponed_app_tools_import(postponed_application_tools: List[ApplicationImportCompoundTool], postponed_id_mapper, project_id):
    rpc_call = rpc_tools.RpcMixin().rpc.call

    incomplete_apps = {}
    already_connected_info = []
    errors = []
    result_candidates = {}
    for original_entity_index, tools in postponed_application_tools:
        for tool in tools:
            app_id = app_ver_id = connected_app_id = None
            try:
                app_id, app_ver_id = tool.get_real_application_ids(postponed_id_mapper)
                if app_id in incomplete_apps:
                    continue
                payload, connected_app_id = tool.generate_create_payload(postponed_id_mapper)
                result = rpc_call.applications_add_application_tool(
                    payload,
                    project_id,
                    app_ver_id,
                    return_details=True
                )
                if not result['ok']:
                    raise RuntimeError(result['error'])
                else:
                    # the most recent tools update overwrites result with the most actual data
                    result_candidates[app_id] = _wrap_import_result(original_entity_index, result['details'])
                    if connected_app_id is not None:
                        already_connected_info.append((app_id, connected_app_id, original_entity_index))
            except Exception as ex:
                # if some tool can not be added to app, mark all app as failed and delete it
                errors.append(_wrap_import_error(original_entity_index, str(ex)))
                if app_id is not None:
                    incomplete_apps[app_id] = original_entity_index

    failed, good = _recalculate_failed_good_results(incomplete_apps, already_connected_info)

    for app_id, original_entity_index in failed.items():
        try:
            if rpc_call.applications_delete_application(project_id, app_id):
                errors.append(_wrap_import_error(original_entity_index, "Failed because of failed dependant tool"))
            else:
                raise RuntimeError(f"Can not delete {app_id=}")
        except Exception as ex2:
            errors.append(_wrap_import_error(original_entity_index, str(ex2)))

    results = []
    for app_id, _, original_entity_index in good:
        for details in result_candidates.values():
            if details['index'] == original_entity_index:
                results.append(details)

    return results, errors
