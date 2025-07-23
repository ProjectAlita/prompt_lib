from typing import List
from pydantic.v1 import parse_obj_as
from pylon.core.tools import web, log

from ..models.pd.legacy.tag import PromptTagModel
from tools import rpc_tools, db

from ...promptlib_shared.models.all import Tag


def get_all_tags(project_id: int) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        query = session.query(Tag)
        as_dict = lambda x: {'id': x.id, 'tag': x.name, 'color': x.data.get('color')}
        return [as_dict(tag) for tag in query.all()]


def _delete_unused_tags(session):
    tags = session.query(Tag).all()
    for tag in tags:
        if not tag.prompt_version:
            session.delete(tag)


def update_tags(
        project_id: int, prompt_id: int, tags: List[dict], version_name: str = 'latest'
) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        tags = parse_obj_as(List[PromptTagModel], tags)
        for new_tag in tags:
            new_tag = {'name': new_tag.tag, 'data': {'color': new_tag.color}}
            tag = session.query(Tag).filter_by(name=new_tag['name']).first()
            if not tag:
                tag = Tag(**new_tag)
            version.tags.append(tag)
        _delete_unused_tags(session)
        session.commit()
        return [tag.to_json() for tag in version.tags]
