import json
from typing import List
from tools import db
from pylon.core.tools import log
from ..models.all import (
    SearchRequest, 
    Prompt, 
    PromptTag, 
    PromptVersion,
    PromptVersionTagAssociation, 
    Collection,
)
from sqlalchemy import desc, asc, or_, and_, func, distinct, cast, String
from tools import api_tools
from flask import request
from sqlalchemy.orm import joinedload
from .collections import NotFound


def list_search_requests(project_id, args):
    limit = args.get('limit', default=5, type=int)
    offset = args.get('offset', default=0, type=int)
    sort_order = args.get('sort_order', "desc")
    sort_by = args.get('sort_by', "count")

    with db.with_project_schema_session(project_id) as session:
        query = session.query(SearchRequest)
        total = query.count()
        sort_fun = desc if sort_order == "desc" else asc
        query = query.order_by(sort_fun(getattr(SearchRequest, sort_by)))
        query = query.limit(limit).offset(offset)
        return total, query.all()


def get_search_options(project_id, Model, PDModel, joinedload_, args_prefix, filters = None):
    query = request.args.get('query', '')
    search_query = f"%{query}%"

    # filter_fields = ('name', 'title')
    # conditions = []
    # for field in filter_fields:
    #     if hasattr(Model, field):
    #         conditions.append(
    #             getattr(Model, field).ilike(search_query)
    #         )
    # or_(*conditions)

    filter_ = and_(getattr(Model, 'name').ilike(search_query), *filters)
    args_data = get_args(args_prefix)
    total, res = api_tools.get(
        project_id=project_id,
        args=args_data,
        data_model=Model,
        custom_filter=filter_,
        joinedload_=joinedload_,
        is_project_schema=True
    )
    parsed = PDModel(items=res)
    return {
        "total": total,
        "rows": [json.loads(prompt.json()) for prompt in parsed.items]
    }


def get_tag_filter(
        project_id, 
        author_id: int=None, 
        statuses: List[str]=None,
        tags: List[int] = None, 
        session=None
    ):
    if session is None:
        session = db.get_project_schema_session(project_id)

    prompt_query = (
        session.query(Prompt)
        .options(joinedload(Prompt.versions))
    )

    filters = []
    if author_id:
        filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))
    
    if statuses:
        filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))

    if tags:
        prompt_ids = get_prompt_ids_by_tags(project_id, tags, session)
        filters.append(
            Prompt.id.in_(prompt_ids)
        )
        
    prompt_query = prompt_query.filter(*filters)
    prompt_query = prompt_query.with_entities(Prompt.id)
    prompt_subquery = prompt_query.subquery()
    

    query = (
        session.query(PromptTag.id)
        .filter(PromptVersion.prompt_id.in_(prompt_subquery))
        .join(PromptVersionTagAssociation, PromptVersionTagAssociation.c.tag_id == PromptTag.id)
        .join(PromptVersion, PromptVersion.id == PromptVersionTagAssociation.c.version_id)
        .group_by(PromptTag.id)
    ).subquery()
    return PromptTag.id.in_(query)

def get_prompt_ids_by_tags(project_id, tags: List[int], session=None):
    if session is None:
        session = db.get_project_schema_session(project_id)

    prompts =  (
        session.query(Prompt.id)
        .join(Prompt.versions)
        .join(PromptVersion.tags)
        .filter(PromptTag.id.in_(tags))
        .group_by(Prompt.id)
        .having(
            func.count(distinct(PromptTag.id)) == len(tags)
        )
        .all()
    )
    prompt_ids = [prompt.id for prompt in prompts]
    
    session.close()
    return prompt_ids


def get_filter_collection_by_tags_condition(project_id: int, tags: List[int], session=None):
    if session is None:
        session = db.get_project_schema_session(project_id)

    prompt_ids = get_prompt_ids_by_tags(project_id, tags, session)

    if not prompt_ids:
        raise NotFound("No prompt with given tags found")

    prompt_filters = []
    for id_ in prompt_ids:
        prompt_value = {
            "owner_id": project_id,
            "id": id_
        }
        prompt_filters.append(Collection.prompts.contains([prompt_value]))
    
    session.close()
    return or_(*prompt_filters)


def get_args(prefix):
    args = request.args
    limit = args.get('limit', 10, type=int)
    offset = args.get('offset', 0, type=int)
    sort = args.get('sort')
    order = args.get('order')

    result_args = dict(args)
    result_args['limit'] = result_args.get(f'{prefix}_limit', limit)
    result_args['offset'] = result_args.get(f'{prefix}_offset', offset)
    result_args['sort'] = result_args.get(f'{prefix}_sort', sort)
    result_args['order'] = result_args.get(f'{prefix}_order', order)
    return result_args