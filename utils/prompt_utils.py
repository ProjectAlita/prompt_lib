from json import loads
from typing import List
from sqlalchemy import func, cast, String
from sqlalchemy.orm import joinedload

from tools import db
from pylon.core.tools import log

from ..models.all import PromptVariable
from ..models.pd.legacy.variable import VariableModel
from ..models.all import Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag, PromptVersionTagAssociation


def create_variables_bulk(project_id: int, variables: List[dict], **kwargs) -> List[dict]:
    result = []
    with db.with_project_schema_session(project_id) as session:
        for i in variables:
            variable_data = VariableModel.parse_obj(i)
            variable = PromptVariable(
                prompt_version_id=variable_data.prompt_id,
                name=variable_data.name,
                value=variable_data.value
            )
            result.append(variable)
            session.add(variable)
        session.commit()
        return [i.to_json() for i in result]


def prompts_create_variable(project_id: int, variable: dict, **kwargs) -> dict:
    return create_variables_bulk(project_id, [variable])[0]


def get_all_ranked_tags(project_id, top_n=20):
    with db.with_project_schema_session(project_id) as session:
        query = (
            session.query(
                PromptTag.name,
                cast(PromptTag.data, String),
                func.count(func.distinct(PromptVersion.prompt_id))
            )
            .join(PromptVersionTagAssociation, PromptVersionTagAssociation.c.tag_id == PromptTag.id)
            .join(PromptVersion, PromptVersion.id == PromptVersionTagAssociation.c.version_id)
            .group_by(PromptTag.name, cast(PromptTag.data, String))
            .order_by(func.count(func.distinct(PromptVersion.prompt_id)).desc())
            .limit(top_n)
        )
        as_dict = lambda x: {'name': x[0], 'data': loads(x[1]), 'prompt_count': x[2]}
        return [as_dict(i) for i in query.all()]
