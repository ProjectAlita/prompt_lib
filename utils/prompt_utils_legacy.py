import re
from flask import g
from jinja2 import Environment, meta, DebugUndefined
from typing import Optional, List
from pydantic import parse_obj_as
from pylon.core.tools import web, log


from ..models.pd.base import (
    ModelInfoBaseModel,
    ModelSettingsBaseModel,
    PromptVersionBaseModel,
)
from ..models.pd.create import PromptVersionCreateModel, PromptCreateModel
from ..models.pd.update import PromptUpdateModel
from ..models.pd.legacy.tag import PromptTagModel
from ..models.all import Prompt, PromptTag, PromptVersion, PromptVersionTagAssociation
from ..models.pd.v1_structure import (
    PromptV1Model,
    PromptCreateV1Model,
    PromptUpdateV1Model,
    PromptUpdateNameV1Model,
)
from traceback import format_exc
from tools import rpc_tools, db


def prompts_create_prompt(project_id: int, prompt_data: dict, **kwargs) -> dict:
    prompt_data["project_id"] = project_id
    prompt_old_data = PromptCreateV1Model.validate(prompt_data)

    if prompt_old_data.model_settings:
        model_data = ModelInfoBaseModel(
            name=prompt_old_data.model_settings.model_name,
            integration_uid=prompt_old_data.integration_uid,
        )

        model_settings = ModelSettingsBaseModel(
            model=model_data, **prompt_old_data.model_settings.dict()
        )

    else:
        model_settings = None

    prompt_old_data = prompt_old_data.dict(exclude={"project_id"})
    version = PromptVersionCreateModel(
        name="latest",
        author_id=g.auth.id,
        type=prompt_old_data["type"],
        context=prompt_old_data["prompt"],
        model_settings=model_settings,
    ).dict(exclude_unset=True)

    prompt_old_data["versions"] = [version]
    prompt_old_data["owner_id"] = project_id
    prompt_new_data = PromptCreateModel.parse_obj(prompt_old_data)

    with db.with_project_schema_session(project_id) as session:
        prompt = Prompt(
            **prompt_new_data.dict(exclude_unset=True, exclude={"versions"})
        )
        prompt_version = PromptVersion(**version)
        prompt_version.prompt = prompt

        session.add(prompt)
        session.commit()
        return prompt.to_json()


def prompts_update_prompt(project_id: int, prompt: dict, **kwargs) -> bool:
    prompt["project_id"] = project_id
    prompt_old_data = PromptUpdateV1Model.validate(prompt)

    prompt_old_data = prompt_old_data.dict(exclude={"project_id"})
    version = PromptVersionBaseModel(
        name=prompt_old_data["version"],
        author_id=g.auth.id,
        type=prompt_old_data["type"],
        context=prompt_old_data["prompt"],
        model_settings=prompt_old_data["model_settings"],
        embedding_settings=prompt_old_data["embedding_settings"],
    )

    prompt_old_data["owner_id"] = project_id
    prompt_new_data = PromptUpdateModel.parse_obj(prompt_old_data)

    with db.with_project_schema_session(project_id) as session:
        session.query(Prompt).filter(Prompt.id == prompt_new_data.id).update(
            prompt_new_data.dict(exclude={"id", "project_id"}, exclude_none=True)
        )
        session.query(PromptVersion).filter(
            PromptVersion.prompt_id == prompt_new_data.id,
            PromptVersion.name == prompt_old_data["version"],
        ).update(version.dict(exclude_unset=True))

        session.commit()
        updated_prompt = session.query(Prompt).get(prompt_new_data.id)
        return updated_prompt.to_json()


def prompts_update_name(project_id: int, prompt_id: int, prompt_data: dict) -> bool:
    prompt_data = PromptUpdateNameV1Model.validate(prompt_data)
    with db.with_project_schema_session(project_id) as session:
        row_count = (
            session.query(Prompt)
            .filter(
                Prompt.id == prompt_id,
            )
            .update(prompt_data.dict())
        )
        session.commit()
        return bool(row_count)


def prompts_delete_prompt(
    project_id: int, prompt_id: int, version_name: str = "", **kwargs
) -> bool:
    with db.with_project_schema_session(project_id) as session:
        if version_name and version_name != "latest":
            if (
                versions := session.query(PromptVersion)
                .filter(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.name == version_name,
                )
                .all()
            ):
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


def get_tags(project_id: int, prompt_id: int) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        query = (
            session.query(PromptTag)
            .join(
                PromptVersionTagAssociation,
                PromptVersionTagAssociation.c.tag_id == PromptTag.id,
            )
            .join(
                PromptVersion,
                PromptVersion.id == PromptVersionTagAssociation.c.version_id,
            )
            .filter(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.id)
        )
        as_dict = lambda x: {"id": x.id, "tag": x.name, "color": x.data.get("color")}
        return [as_dict(tag) for tag in query.all()]


def get_all_tags(project_id: int) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        query = session.query(PromptTag)
        as_dict = lambda x: {"id": x.id, "tag": x.name, "color": x.data.get("color")}
        return [as_dict(tag) for tag in query.all()]


def _delete_unused_tags(session):
    tags = session.query(PromptTag).all()
    for tag in tags:
        if not tag.prompt_version:
            session.delete(tag)


def update_tags(
    project_id: int, prompt_id: int, tags: List[dict], version_name: str = "latest"
) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        if (
            version := session.query(PromptVersion)
            .filter(
                PromptVersion.prompt_id == prompt_id, PromptVersion.name == version_name
            )
            .one_or_none()
        ):
            version.tags.clear()
        tags = parse_obj_as(List[PromptTagModel], tags)
        for new_tag in tags:
            new_tag = {"name": new_tag.tag, "data": {"color": new_tag.color}}
            tag = session.query(PromptTag).filter_by(name=new_tag["name"]).first()
            if not tag:
                tag = PromptTag(**new_tag)
            version.tags.append(tag)
        _delete_unused_tags(session)
        session.commit()
        return [tag.to_json() for tag in version.tags]
