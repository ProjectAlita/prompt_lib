from json import loads
import json
from typing import List, Optional
from sqlalchemy import func, cast, String
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from tools import db
from pylon.core.tools import log

from ..models.all import (
    Prompt,
    PromptVersion,
    PromptVariable,
    PromptMessage,
    PromptTag,
    PromptVersionTagAssociation,
)
from ..models.pd.legacy.variable import VariableModel
from ..models.pd.update import PromptVersionUpdateModel
from ..models.pd.detail import PromptVersionDetailModel
from ..models.pd.list import PromptTagListModel


def create_variables_bulk(
    project_id: int, variables: List[dict], **kwargs
) -> List[dict]:
    result = []
    with db.with_project_schema_session(project_id) as session:
        for i in variables:
            variable_data = VariableModel.parse_obj(i)
            variable = PromptVariable(
                prompt_version_id=variable_data.prompt_id,
                name=variable_data.name,
                value=variable_data.value,
            )
            result.append(variable)
            session.add(variable)
        session.commit()
        return [i.to_json() for i in result]


def prompts_create_variable(project_id: int, variable: dict, **kwargs) -> dict:
    return create_variables_bulk(project_id, [variable])[0]


def get_prompt_tags(project_id: int, prompt_id: int) -> List[dict]:
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
        return [PromptTagListModel.from_orm(tag).dict() for tag in query.all()]


def get_all_ranked_tags(project_id: int, top_n: int = 20) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        query = (
            session.query(
                PromptTag.id,
                PromptTag.name,
                cast(PromptTag.data, String),
                func.count(func.distinct(PromptVersion.prompt_id)),
            )
            .join(
                PromptVersionTagAssociation,
                PromptVersionTagAssociation.c.tag_id == PromptTag.id,
            )
            .join(
                PromptVersion,
                PromptVersion.id == PromptVersionTagAssociation.c.version_id,
            )
            .group_by(PromptTag.id, PromptTag.name, cast(PromptTag.data, String))
            .order_by(func.count(func.distinct(PromptVersion.prompt_id)).desc())
            .limit(top_n)
        )
        as_dict = lambda x: {
            "id": x[0],
            "name": x[1],
            "data": loads(x[2]),
            "prompt_count": x[3],
        }
        return [as_dict(tag) for tag in query.all()]


def _update_related_table(session, version, version_data, db_model):
    added_ids = set()
    existing_entities = (
        session.query(db_model)
        .filter(db_model.id.in_({i.id for i in version_data if i.id}))
        .all()
    )
    existing_entities_map = {i.id: i for i in existing_entities}

    for pd_model in version_data:
        if pd_model.id in existing_entities_map:
            entity = existing_entities_map[pd_model.id]
            for key, value in pd_model.dict(exclude={"id"}).items():
                setattr(entity, key, value)
        else:
            entity = db_model(**pd_model.dict())
            entity.prompt_version = version
            session.add(entity)
        session.flush()
        added_ids.add(entity.id)

    usused_entities = (
        session.query(db_model)
        .filter(db_model.prompt_version_id == version.id, db_model.id.not_in(added_ids))
        .all()
    )
    for entity in usused_entities:
        session.delete(entity)


def prompts_update_version(
    project_id: int, version_data: PromptVersionUpdateModel
) -> dict:
    with db.with_project_schema_session(project_id) as session:
        if version_data.id:
            version: PromptVersion = (
                session.query(PromptVersion)
                .filter(PromptVersion.id == version_data.id)
                .first()
            )
        else:
            version: PromptVersion = (
                session.query(PromptVersion)
                .filter(
                    PromptVersion.prompt_id == version_data.prompt_id,
                    PromptVersion.name == version_data.name,
                )
                .first()
            )
            version_data.id = version.id
        if not version:
            return {
                "updated": False,
                "msg": f"Prompt version with id {version_data.id} not found",
            }
        if version.name != "latest":
            return {
                "updated": False,
                "msg": "Only latest prompt version can be updated",
            }

        for key, value in version_data.dict(
            exclude={"variables", "messages", "tags"}
        ).items():
            setattr(version, key, value)

        # Updating variables
        result_variables = []
        for update_var in version_data.variables:
            for existing_var in version.variables:
                if existing_var.name == update_var.name:
                    existing_var.value = update_var.value
                    result_variables.append(existing_var)
                    break
            else:
                variable = PromptVariable(**update_var.dict())
                variable.prompt_version = version
                result_variables.append(variable)
        version.variables = result_variables

        try:
            _update_related_table(
                session, version, version_data.messages, PromptMessage
            )

            version.tags.clear()
            existing_tags = (
                session.query(PromptTag)
                .filter(PromptTag.name.in_({i.name for i in version_data.tags}))
                .all()
            )
            existing_tags_map = {i.name: i for i in existing_tags}
            for tag in version_data.tags:
                prompt_tag = existing_tags_map.get(tag.name, PromptTag(**tag.dict()))
                version.tags.append(prompt_tag)

            session.add(version)
            session.commit()
        except IntegrityError as e:
            log.error(e)
            return {
                "updated": False,
                "msg": "Values you passed violates unique constraint",
            }

        result = PromptVersionDetailModel.from_orm(version)
        return {"updated": True, "data": loads(result.json())}


def list_prompts(
    project_id: int,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filters: Optional[list] = None,
):
    if filters is None:
        filters = []

    with db.with_project_schema_session(project_id) as session:
        query = session.query(Prompt).options(
            joinedload(Prompt.versions).joinedload(PromptVersion.tags)
        )

        if filters:
            query = query.filter(*filters)

        # Apply sorting
        if sort_order.lower() == "asc":
            query = query.order_by(getattr(Prompt, sort_by))
        else:
            query = query.order_by(getattr(Prompt, sort_by).desc())

        total = query.count()
        # Apply limit and offset for pagination
        query = query.limit(limit).offset(offset)
        prompts: List[Prompt] = query.all()
    return total, prompts
