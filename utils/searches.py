import json
from flask import request
from typing import List
from tools import db
from pylon.core.tools import log
from ..models.all import (
    SearchRequest,
    Prompt,
    PromptVersion,
    PromptVersionTagAssociation,
    Collection,
)
from ..models.pd.collections import MultipleCollectionSearchModel
from ..models.pd.misc import MultiplePromptTagListModel
from sqlalchemy import desc, asc, or_, and_, func, distinct
from tools import api_tools
from flask import request
from sqlalchemy.orm import joinedload
from .expceptions import NotFound
from .collections import get_filter_collection_by_entity_tags_condition
from ...promptlib_shared.models.all import Tag
from ...promptlib_shared.utils.utils import get_entities_by_tags

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


def get_search_options(project_id, Model, PDModel, joinedload_, args_prefix, filters=None):
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


def get_search_options_one_entity(
    project_id,
    entity_name,
    Model,
    ModelVersion,
    MultipleSearchModel,
    ModelVersionTagAssociation
):
    result = {}
    entities = request.args.getlist('entities[]')
    tags = tuple(set(int(tag) for tag in request.args.getlist('tags[]')))
    statuses = request.args.getlist('statuses[]')
    author_id = request.args.get("author_id", type=int)

    meta_data = {
        entity_name: {
            "Model": Model,
            "PDModel": MultipleSearchModel,
            "joinedload_": [Model.versions],
            "args_prefix": entity_name,
            "filters": [],
        },
        "collection": {
            "Model": Collection,
            "PDModel": MultipleCollectionSearchModel,
            "joinedload_": None,
            "args_prefix": "col",
            "filters": [],
        },
        "tag": {
            "Model": Tag,
            "PDModel": MultiplePromptTagListModel,
            "joinedload_": None,
            "args_prefix": "tag",
            "filters": []
        }
    }

    if tags:
        try:
            data = get_filter_collection_by_entity_tags_condition(project_id, tags, entity_name)
            meta_data['collection']['filters'].append(or_(*data))
        except NotFound:
            entities = [entity for entity in entities if entity != "collection"]
            result['collection'] = {
                "total": 0,
                "rows": []
            }

        entities_subq = get_entities_by_tags(project_id, tags, Model, ModelVersion)
        meta_data[entity_name]['filters'].append(
            Model.id.in_(entities_subq)
        )

    if author_id:
        meta_data['collection']['filters'].append(
            Collection.author_id == author_id
        )

        meta_data[entity_name]['filters'].append(
            Model.versions.any(ModelVersion.author_id == author_id)
        )

    if statuses:
        meta_data[entity_name]['filters'].append(
            (Model.versions.any(ModelVersion.status.in_(statuses)))
        )
        meta_data['collection']['filters'].append(
            Collection.status.in_(statuses)
        )

    meta_data['tag']['filters'].append(
        get_tag_filter(
            project_id=project_id,
            entity_name=entity_name,
            Model=Model,
            ModelVersion=ModelVersion,
            ModelVersionTagAssociation=ModelVersionTagAssociation,
            author_id=author_id,
            statuses=statuses,
            tags=tags,

        )
    )

    for section, data in meta_data.items():
        if section in entities:
            result[section] = get_search_options(project_id, **data)

    return result


def get_tag_filter(
        project_id,
        entity_name,
        Model,
        ModelVersion,
        ModelVersionTagAssociation,
        author_id: int = None,
        statuses: List[str] = None,
        tags: List[int] = None,
        session=None
):
    if session is None:
        session = db.get_project_schema_session(project_id)

    entity_query = (
        session.query(Model)
        .options(joinedload(Model.versions))
    )

    filters = []
    if author_id:
        filters.append(Model.versions.any(ModelVersion.author_id == author_id))

    if statuses:
        filters.append(Model.versions.any(ModelVersion.status.in_(statuses)))

    if tags:
        entities_subq = get_entities_by_tags(project_id, tags, Model, ModelVersion, session)
        filters.append(
            Model.id.in_(entities_subq)
        )

    entity_query = entity_query.filter(*filters)
    entity_query = entity_query.with_entities(Model.id)
    entity_subquery = entity_query.subquery()

    query = (
        session.query(Tag.id)
        .filter(getattr(ModelVersion, f'{entity_name}_id').in_(entity_subquery))
        .join(ModelVersionTagAssociation, ModelVersionTagAssociation.c.tag_id == Tag.id)
        .join(ModelVersion, ModelVersion.id == ModelVersionTagAssociation.c.version_id)
        .group_by(Tag.id)
    ).subquery()
    return Tag.id.in_(query)


def get_filter_collection_by_prompt_tags_condition(project_id: int, tags: List[int], session=None):
    filters = get_filter_collection_by_entity_tags_condition(
        project_id,
        tags,
        'prompt',
        session
    )
    return or_(*filters)


def get_args(prefix):
    args = request.args
    limit = args.get('limit', 0, type=int)
    offset = args.get('offset', 0, type=int)
    sort = args.get('sort')
    order = args.get('order', 'desc')

    result_args = dict(args)
    result_args['limit'] = result_args.get(f'{prefix}_limit', limit)
    result_args['offset'] = result_args.get(f'{prefix}_offset', offset)
    result_args['sort'] = result_args.get(f'{prefix}_sort', sort)
    result_args['order'] = result_args.get(f'{prefix}_order', order)
    return result_args
