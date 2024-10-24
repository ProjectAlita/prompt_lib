from typing import List
from sqlalchemy.orm import joinedload

from tools import db
from pylon.core.tools import log

from ..models.all import Prompt, PromptVersion
from ..models.pd.export_import import (
    PromptExportModel, DialExportModel,
    DialPromptExportModel, DialModelExportModel, PromptForkModel,
)
from ..models.pd.model_settings import ModelSettingsBaseModel


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
