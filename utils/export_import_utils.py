from typing import List
from sqlalchemy.orm import joinedload

from tools import db
from pylon.core.tools import log

from ..models.all import Prompt, PromptVersion, Collection
from ..models.pd.base import PromptVersionBaseModel
from ..models.pd.export_import import (
    DialImportModel,
    DialModelImportModel,
    DialPromptImportModel,
    PromptExportModel,
)
from ..utils.create_utils import create_version
from ..utils.collections import group_by_project_id


def prompts_export_to_dial(project_id: int, prompt_id: int = None, session=None) -> dict:
    if session is None:
        session = db.get_project_schema_session(project_id)

    filters = [Prompt.id == prompt_id] if prompt_id else []
    prompts: List[Prompt] = session.query(Prompt).filter(*filters).options(
        joinedload(Prompt.versions)).all()

    prompts_to_export = []
    for prompt in prompts:
        prompt_data = prompt.to_json()
        export_data = {**prompt_data}
        for version in prompt.versions:
            export_data['content'] = version.context or ''
            if version.model_settings:
                export_data['model'] = DialModelImportModel(
                    id=version.model_settings.get('model', {}).get('name', '')
                    )
        
        prompts_to_export.append(DialPromptImportModel(**export_data))
    result = DialImportModel(prompts=prompts_to_export, folders=[])
    session.close()

    return result.dict()


def collection_export(project_id: int, collection_id: int, to_dail=False):
    with db.with_project_schema_session(project_id) as session:
        collection = session.query(Collection).get(collection_id)
        if not collection:
            raise Exception(f"Collection with id '{collection_id}' not found")
        grouped_prompts = group_by_project_id(collection.prompts)
        result_prompts = []
        for project_id, prompts in grouped_prompts.items():
            with db.with_project_schema_session(project_id) as session2:
                for prompt_id in prompts:
                    if to_dail:
                        result = prompts_export_to_dial(project_id, prompt_id, session2)
                    else:
                        result = prompts_export(project_id, prompt_id, session2)
                        del result['collections']
                    result_prompts.extend(result['prompts'])    

        folder = {
            "name": collection.name,
            "description": collection.description,
        }
        if to_dail:
             folder['type'] = "prompt"
        return {"prompts": result_prompts, "folders": [folder]}


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
