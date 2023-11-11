import re
from flask import g
from jinja2 import Environment, meta, DebugUndefined
from typing import Optional, List
from pylon.core.tools import web, log


from ..models.pd.base import ModelInfoBaseModel, ModelSettingsBaseModel, PromptVersionBaseModel
from ..models.pd.create import PromptVersionCreateModel, PromptCreateModel
from ..models.pd.update import PromptUpdateModel
from ..models.all import Prompt, PromptVersion
from ..models.pd.v1_structure import (
    PromptV1Model,
    PromptCreateV1Model,
    PromptUpdateV1Model,
    PromptUpdateNameV1Model,
)
from traceback import format_exc
from tools import rpc_tools, db



def prompts_create_prompt(project_id: int, prompt_data: dict, **kwargs) -> dict:
    author_id = g.auth.id
    prompt_data['project_id'] = project_id
    prompt_old_data = PromptCreateV1Model.validate(prompt_data)

    if prompt_old_data.model_settings:
        log.info(f'{prompt_old_data.model_settings=}')
        model_data = ModelInfoBaseModel(
            name=prompt_old_data.model_settings.model_name,
            integration_uid=prompt_old_data.integration_uid
        )
        log.info(f'{model_data=}')
        model_settings = ModelSettingsBaseModel(model=model_data, **prompt_old_data.model_settings.dict())
        log.info(f'{model_settings=}')
    else:
        model_settings = None

    prompt_old_data = prompt_old_data.dict(exclude={'project_id'})
    version = PromptVersionCreateModel(
        name='latest',
        author_id=author_id,
        type=prompt_old_data['type'],
        context=prompt_old_data['prompt'],
        model_settings=model_settings
    ).dict(exclude_unset=True)

    prompt_old_data['versions'] = [version]
    prompt_old_data['owner_id'] = author_id
    prompt_new_data = PromptCreateModel.parse_obj(prompt_old_data)

    with db.with_project_schema_session(project_id) as session:
        prompt = Prompt(**prompt_new_data.dict(
            exclude_unset=True,
            exclude={'versions'}
        ))
        prompt_version = PromptVersion(**version)
        prompt_version.prompt = prompt

        session.add(prompt)
        session.commit()
        return prompt.to_json()


def prompts_update_prompt(project_id: int, prompt: dict, **kwargs) -> bool:
    author_id = g.auth.id
    prompt['project_id'] = project_id
    prompt_old_data = PromptUpdateV1Model.validate(prompt)

    prompt_old_data = prompt_old_data.dict(exclude={'project_id'})
    version = PromptVersionBaseModel(
        name=prompt_old_data['version'],
        author_id=author_id,
        type=prompt_old_data['type'],
        context=prompt_old_data['prompt'],
        model_settings=prompt_old_data['model_settings'],
        embedding_settings=prompt_old_data['embedding_settings']
    )

    prompt_old_data['owner_id'] = author_id
    prompt_new_data = PromptUpdateModel.parse_obj(prompt_old_data)

    with db.with_project_schema_session(project_id) as session:
        session.query(Prompt).filter(Prompt.id == prompt_new_data.id).update(
            prompt_new_data.dict(exclude={'id', 'project_id'}, exclude_none=True)
        )
        session.query(PromptVersion).filter(
            PromptVersion.prompt_id == prompt_new_data.id,
            PromptVersion.name == prompt_old_data['version']
            ).update(version.dict(exclude_unset=True))

        session.commit()
        updated_prompt = session.query(Prompt).get(prompt_new_data.id)
        return updated_prompt.to_json()


def prompts_update_name(project_id: int, prompt_id: int, prompt_data: dict) -> bool:
    prompt_data = PromptUpdateNameV1Model.validate(prompt_data)
    with db.with_project_schema_session(project_id) as session:
        row_count = session.query(Prompt).filter(
            Prompt.id == prompt_id,
            ).update(prompt_data.dict())
        session.commit()
        return bool(row_count)


def prompts_delete_prompt(project_id: int, prompt_id: int, version_name: str = '', **kwargs) -> bool:
    with db.with_project_schema_session(project_id) as session:
        if version_name and version_name != 'latest':
            if versions := session.query(PromptVersion).filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.name == version_name
            ).all():
                for version in versions:
                    session.delete(version)
                session.commit()
                return True
        else:
            if prompt := session.query(Prompt).get(prompt_id):
                session.delete(prompt)
                session.commit()
                return True
    return False
