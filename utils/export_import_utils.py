from typing import List
from sqlalchemy.orm import joinedload
from pydantic import ValidationError
from pydantic.utils import deep_update

from tools import db, rpc_tools

from ..models.all import Prompt, PromptVersion
from ..models.pd.export_import import (
    PromptExportModel, DialExportModel,
    DialPromptExportModel, DialModelExportModel, PromptForkModel,
)
from ..models.pd.import_wizard import ApplicationImportCompoundTool, IMPORT_MODEL_ENTITY_MAPPER
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


def _postponed_app_tools_import(postponed_application_tools: List[ApplicationImportCompoundTool], postponed_id_mapper, project_id):
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


def import_wizard(import_data: dict, project_id: int, author_id: int):
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
    for item in import_data:
        postponed_tools = []
        entity = item['entity']
        entity_model = IMPORT_MODEL_ENTITY_MAPPER.get(entity)
        if entity_model:
            try:
                model = entity_model.parse_obj(item)
            except ValidationError as e:
                return result, {entity: [f'Validation error on item {entity}: {e}']}
        else:
            return result, {entity: [f'No such {entity} in import entity mapper']}

        if entity == 'agents':
            postponed_tools = model.postponed_tools
            postponed_application_tools.extend(postponed_tools)

        model_data = model.dict()

        rpc_func = ENTITY_IMPORT_MAPPER.get(entity)
        if rpc_func:
            r, e = getattr(rpc_call, rpc_func)(
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
        tool_results, tool_errors = _postponed_app_tools_import(
            postponed_application_tools,
            postponed_id_mapper,
            project_id
        )
        result['agents'].extend(tool_results)
        errors['agents'].extend(tool_errors)

    return result, errors
