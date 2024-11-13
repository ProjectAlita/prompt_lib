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


def _postponed_app_tools_import(postponed_application_tools: List[ApplicationImportCompoundTool], postponed_id_mapper, project_id):
    rpc_call = rpc_tools.RpcMixin().rpc.call

    deleted_incomplete_apps = set()
    errors = []
    results = {}
    for original_entity_index, tools in postponed_application_tools:
        for tool in tools:
            app_id = app_ver_id = None
            try:
                app_id, app_ver_id = tool.get_real_application_ids(postponed_id_mapper)
                payload = tool.generate_create_payload(postponed_id_mapper)
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
                    results[app_ver_id] = _wrap_import_result(original_entity_index, result['details'])
            except Exception as ex:
                # if some tool can not be added to app, mark all app as failed and delete it
                errors.append(_wrap_import_error(original_entity_index, str(ex)))
                if app_id is not None and app_id not in deleted_incomplete_apps:
                    try:
                        if rpc_call.applications_delete_application(project_id, app_id):
                            deleted_incomplete_apps.add(app_id)
                            # TODO: delete from postponed_id_mapper
                    except Exception as ex2:
                        errors.append(_wrap_import_error(original_entity_index, str(ex2)))

    return results.values(), errors
