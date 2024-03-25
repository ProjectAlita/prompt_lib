from typing import List
from sqlalchemy.orm import joinedload

from tools import db
from pylon.core.tools import log

from ..models.all import Prompt, PromptVersion
from ..models.pd.export_import import (
    PromptExportModel, DialExportModel,
    DialPromptExportModel, DialModelExportModel,
)


def prompts_export_to_dial(project_id: int, prompt_id: int = None, session=None) -> dict:
    if session is None:
        session = db.get_project_schema_session(project_id)

    filters = [Prompt.id == prompt_id] if prompt_id else []
    prompts: List[Prompt] = session.query(Prompt).filter(*filters).options(
        joinedload(Prompt.versions)).all()

    prompts_to_export = []
    for prompt in prompts:
        # prompt_data = prompt.to_json()
        # export_data = {**prompt_data}
        export_data = DialPromptExportModel(
            id=prompt.id,
            name=prompt.name,
            description=prompt.description,
            content='',
            model={}
        )
        for version in prompt.versions:
            export_data.content = version.context or export_data.content
            if version.model_settings:
                export_data.model = DialModelExportModel(
                    id=version.model_settings.get('model', {}).get('name', '')
                )
        prompts_to_export.append(export_data.dict())
    result = DialExportModel(prompts=prompts_to_export, folders=[])
    session.close()

    return result.dict()



def prompts_export(project_id: int, prompt_id: int = None, session=None) -> dict:
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
        prompt_data = PromptExportModel.from_orm(prompt)
        prompts_to_export.append(prompt_data.dict())

    session.close()
    return {'prompts': prompts_to_export, 'collections': []}
