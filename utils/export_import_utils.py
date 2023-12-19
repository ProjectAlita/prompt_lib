import json
from typing import List
from flask import g
from sqlalchemy.orm import joinedload

from tools import db
from pylon.core.tools import log

from ..models.all import Prompt, PromptVersion
from ..models.pd.base import PromptBaseModel, PromptVersionBaseModel
from ..models.pd.export_import import DialImportModel, DialModelImportModel, DialPromptImportModel
from ..utils.create_utils import create_version


def prompts_export_to_dial(project_id: int, prompt_id: int = None) -> dict:
    with db.with_project_schema_session(project_id) as session:
        filters = [Prompt.id == prompt_id] if prompt_id else []
        prompts: List[Prompt] = session.query(Prompt).filter(*filters).options(
            joinedload(Prompt.versions)).all()

        prompts_to_export = []
        for prompt in prompts:
            prompt_data = prompt.to_json()
            for version in prompt.versions:
                export_data = {
                    'content': version.context or '',
                    **prompt_data
                }
                if version.model_settings:
                    export_data['model'] = DialModelImportModel(
                        id=version.model_settings.get('model', {}).get('name', '')
                        )
                prompts_to_export.append(DialPromptImportModel(**export_data))

        result = DialImportModel(prompts=prompts_to_export, folders=[])
        return result.dict()


def prompts_export(project_id: int, prompt_id: int = None) -> dict:
    with db.with_project_schema_session(project_id) as session:
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
            prompt_data = PromptBaseModel.from_orm(prompt)

            prompts_to_export.append(prompt_data.dict())

        return {'prompts': prompts_to_export, 'collections': []}


def prompts_import_from_dial(project_id: int, prompt_data: dict, session: None) -> Prompt:
    prompt = Prompt(
        name=prompt_data['name'],
        description=prompt_data.get('description'),
        owner_id=project_id
    )
    ver = PromptVersionBaseModel(
        name='latest',
        author_id=prompt_data['author_id'],
        context=prompt_data['content'],
        type='chat'
    )
    create_version(ver, prompt=prompt, session=session)
    if session:
        session.add(prompt)
        session.flush()
    return prompt
