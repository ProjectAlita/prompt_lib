from json import loads
from datetime import datetime
from typing import List, Optional, Union, Tuple, Dict, Literal, Generator
from werkzeug.datastructures import MultiDict
from sqlalchemy import func, cast, String, desc, or_, asc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from tools import db, auth, rpc_tools
from pylon.core.tools import log

from .like_utils import add_likes, add_trending_likes, add_my_liked
from ..models.all import Collection, Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag, \
    PromptVersionTagAssociation
from ..models.pd.legacy.variable import VariableModel
from ..models.pd.update import PromptVersionUpdateModel
from ..models.pd.detail import PromptDetailModel, PromptVersionDetailModel, PublishedPromptDetailModel
from ..models.pd.list import PromptTagListModel
from ..models.enums.all import PromptVersionStatus


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


def get_prompt_tags(project_id: int, prompt_id: int) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        query = (
            session.query(PromptTag)
            .join(PromptVersionTagAssociation, PromptVersionTagAssociation.c.tag_id == PromptTag.id)
            .join(PromptVersion, PromptVersion.id == PromptVersionTagAssociation.c.version_id)
            .filter(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.id)
        )
        return [PromptTagListModel.from_orm(tag).dict() for tag in query.all()]


def _flatten_prompt_ids(project_id: int, collection_prompts: List[Dict[str, int]]):
    prompt_ids = []
    for collection_prompt in collection_prompts:
        prompts = collection_prompt[0]
        for prompt in prompts:
            if prompt['owner_id'] == project_id:
                prompt_ids.append(prompt['id'])
    return prompt_ids


def get_all_ranked_tags(project_id: int, args: MultiDict) -> dict:
    # Args to sort prompt subquery:
    limit = args.get("limit", default=10, type=int)
    offset = args.get("offset", default=0, type=int)
    my_liked_collections = args.get("my_liked_collections", default=False, type=bool)
    my_liked_prompts = args.get("my_liked_prompts", default=False, type=bool)

    # trending period
    trend_start_period = args.get('trend_start_period')
    trend_end_period = args.get('trend_end_period')
    trend_period = None
    if trend_start_period:
        trend_end_period = datetime.utcnow() if not trend_end_period else datetime.strptime(trend_end_period, "%Y-%m-%dT%H:%M:%S")
        trend_start_period = datetime.strptime(trend_start_period, "%Y-%m-%dT%H:%M:%S")
        trend_period = (trend_start_period, trend_end_period)

    # Filters to sort prompt subquery:
    filters = []
    if author_id := args.get('author_id'):
        filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))
    if statuses := args.get('statuses'):
        statuses = statuses.split(',')
        filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))
    if query := args.get('query'):
        filters.append(
            or_(
                Prompt.name.ilike(f"%{query}%"),
                Prompt.description.ilike(f"%{query}%")
            )
        )

    with db.with_project_schema_session(project_id) as session:
        if collection_phrase := args.get('collection_phrase'):
            collection_prompts = session.query(Collection.prompts).filter(
                or_(
                    Collection.name.ilike(f"%{collection_phrase}%"),
                    Collection.description.ilike(f"%{collection_phrase}%")
                )
            ).all()
            prompt_ids = prompt_ids = _flatten_prompt_ids(project_id, collection_prompts)
            filters.append(Prompt.id.in_(prompt_ids))

        if my_liked_collections:
            query = session.query(Collection.prompts)
            extra_columns = []

            query, new_columns = add_likes(
                original_query=query,
                project_id=project_id,
                entity_name='collection',
            )
            extra_columns.extend(new_columns)

            query, new_columns = add_my_liked(
                original_query=query,
                project_id=project_id,
                entity_name='collection',
                filter_results=True
            )
            extra_columns.extend(new_columns)
            q_result = query.all()
            prompt_ids = _flatten_prompt_ids(project_id, q_result)
            filters.append(Prompt.id.in_(prompt_ids))

        # Prompt subquery
        prompt_query = (
            session.query(Prompt)
            .options(joinedload(Prompt.versions))
        )
        extra_columns = []
        prompt_query, new_columns = add_likes(
            original_query=prompt_query,
            project_id=project_id,
            entity_name='prompt',
        )
        extra_columns.extend(new_columns)
        if trend_period:
            prompt_query, new_columns = add_trending_likes(
                original_query=prompt_query,
                project_id=project_id,
                entity_name='prompt',
                trend_period=trend_period,
                filter_results=True
            )
            extra_columns.extend(new_columns)
        if my_liked_prompts:
            prompt_query, new_columns = add_my_liked(
                original_query=prompt_query,
                project_id=project_id,
                entity_name='prompt',
                filter_results=True
            )
            extra_columns.extend(new_columns)
        if filters:
            prompt_query = prompt_query.filter(*filters)

        prompt_query = prompt_query.with_entities(Prompt.id)
        prompt_subquery = prompt_query.subquery()

        # Main query
        tag_filters = [PromptVersion.prompt_id.in_(prompt_subquery)]
        if search := args.get("search"):
            tag_filters.append(PromptTag.name.ilike(f"%{search}%"))

        query = (
            session.query(
                PromptTag.id,
                PromptTag.name,
                cast(PromptTag.data, String),
                func.count(func.distinct(PromptVersion.prompt_id))
            )
            .filter(*tag_filters)
            .join(PromptVersionTagAssociation, PromptVersionTagAssociation.c.tag_id == PromptTag.id)
            .join(PromptVersion, PromptVersion.id == PromptVersionTagAssociation.c.version_id)
            .group_by(PromptTag.id, PromptTag.name, cast(PromptTag.data, String))
            .order_by(func.count(func.distinct(PromptVersion.prompt_id)).desc())
        )
        total = query.count()

        # if sort_order.lower() == "asc":
        #     query = query.order_by(getattr(PromptTag, sort_by, sort_by))
        # else:
        #     query = query.order_by(desc(getattr(PromptTag, sort_by, sort_by)))
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        as_dict = lambda x: {'id': x[0], 'name': x[1], 'data': loads(x[2]), 'prompt_count': x[3]}
        return {
            "total": total,
            "rows": [as_dict(tag) for tag in query.all()]
        }


def _update_related_table(session, version, version_data, db_model):
    added_ids = set()
    existing_entities = session.query(db_model).filter(
        db_model.id.in_({i.id for i in version_data if i.id})
    ).all()
    existing_entities_map = {i.id: i for i in existing_entities}

    for pd_model in version_data:
        if pd_model.id in existing_entities_map:
            entity = existing_entities_map[pd_model.id]
            for key, value in pd_model.dict(exclude={'id'}).items():
                setattr(entity, key, value)
        else:
            entity = db_model(**pd_model.dict())
            entity.prompt_version = version
            session.add(entity)
        session.flush()
        added_ids.add(entity.id)

    usused_entities = session.query(db_model).filter(
        db_model.prompt_version_id == version.id,
        db_model.id.not_in(added_ids)
    ).all()
    for entity in usused_entities:
        session.delete(entity)


def prompts_update_version(project_id: int, version_data: PromptVersionUpdateModel) -> dict:
    with db.with_project_schema_session(project_id) as session:
        if version_data.id:
            version: PromptVersion = session.query(PromptVersion).filter(
                PromptVersion.id == version_data.id
            ).first()
        else:
            version: PromptVersion = session.query(PromptVersion).filter(
                PromptVersion.prompt_id == version_data.prompt_id,
                PromptVersion.name == version_data.name,
            ).first()
            version_data.id = version.id
        if not version:
            return {'updated': False, 'msg': f'Prompt version with id {version_data.id} not found'}
        if version.name != 'latest':
            return {'updated': False, 'msg': 'Only latest prompt version can be updated'}

        for key, value in version_data.dict(exclude={'variables', 'messages', 'tags'}).items():
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
            _update_related_table(session, version, version_data.messages, PromptMessage)

            version.tags.clear()
            existing_tags = session.query(PromptTag).filter(
                PromptTag.name.in_({i.name for i in version_data.tags})
            ).all()
            existing_tags_map = {i.name: i for i in existing_tags}
            for tag in version_data.tags:
                prompt_tag = existing_tags_map.get(tag.name, PromptTag(**tag.dict()))
                version.tags.append(prompt_tag)

            session.add(version)
            session.commit()
        except IntegrityError as e:
            log.error(e)
            return {'updated': False, 'msg': 'Values you passed violates unique constraint'}

        result = PromptVersionDetailModel.from_orm(version)
        return {'updated': True, 'data': loads(result.json())}

def set_columns_as_attrs(q_result, extra_columns: list) -> Generator:
    # log.info(f'{extra_columns=}, {q_result=}')
    for i in q_result:
        try:
            entity, *extra_data = i
            for k, v in zip(extra_columns, extra_data):
                # log.info(f'setting {k}={v} to {type(entity)}')
                setattr(entity, k, v)
        except TypeError:
            entity = i
        yield entity

def list_prompts(project_id: int,
                 limit: int | None = 10, offset: int | None = 0,
                 sort_by: str = 'created_at',
                 sort_order: Literal['asc', 'desc'] = 'desc',
                 filters: Optional[list] = None,
                 with_likes: bool = True,
                 my_liked: bool = False,
                 trend_period: Optional[Tuple[datetime, datetime]] = None
                 ) -> Tuple[int, list]:
    if my_liked and not with_likes:
        my_liked = False

    if filters is None:
        filters = []

    with db.with_project_schema_session(project_id) as session:

        # query = (
        #     session.query(Prompt)
        #     .options(joinedload(Prompt.versions).joinedload(PromptVersion.tags))
        #     .options(with_expression(Prompt.likes, func.count(likes_subquery.c.user_id)))
        #     .outerjoin(likes_subquery, likes_subquery.c.entity_id == Prompt.id)
        #     .group_by(Prompt)
        # )

        extra_columns = []

        query = (
            session.query(Prompt)
            .options(joinedload(Prompt.versions).joinedload(PromptVersion.tags))
        )
        sort_by_likes = sort_by == "likes"
        if with_likes:
            query, new_columns = add_likes(
                original_query=query,
                project_id=project_id,
                entity_name='prompt',
                sort_by_likes=sort_by_likes,
                sort_order=sort_order
            )
            extra_columns.extend(new_columns)

        if trend_period:
            query, new_columns = add_trending_likes(
                original_query=query,
                project_id=project_id,
                entity_name='prompt',
                trend_period=trend_period,
                filter_results=True
            )
            extra_columns.extend(new_columns)
        # if my_liked:
        query, new_columns = add_my_liked(
            original_query=query,
            project_id=project_id,
            entity_name='prompt',
            filter_results=my_liked
        )
        extra_columns.extend(new_columns)

        if filters:
            query = query.filter(*filters)

        # Apply sorting
        if not sort_by_likes:
            sort_fn = asc if sort_order.lower() == "asc" else desc
            query = query.order_by(sort_fn(getattr(Prompt, sort_by, sort_by)))

        total = query.count()

        # Apply limit and offset for pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        q_result: List[tuple[Prompt, int, bool, int]] = query.all()

        # if with_likes:
        #     prompts_with_likes = []
        #     for prompt, likes, is_liked, *other in prompts:
        #         prompt.likes = likes
        #         prompt.is_liked = is_liked
        #         if other:
        #             prompt.trending_likes = other[0]
        #         prompts_with_likes.append(prompt)
        #     prompts = prompts_with_likes
        # log.info(f'{q_result=}')


    return total, list(set_columns_as_attrs(q_result, extra_columns))


# def is_personal_project(project_id: int) -> bool:
#     user_id = auth.current_user().get("id")
#     personal_project_id = rpc_tools.RpcMixin().rpc.call.projects_get_personal_project_id(user_id)
#     return personal_project_id == project_id


def get_prompt_details(project_id: int, prompt_id: int, version_name: str = 'latest') -> dict:
    with db.with_project_schema_session(project_id) as session:
        filters = [
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.name == version_name
        ]
        options = [
            joinedload(PromptVersion.prompt).options(joinedload(Prompt.versions)),
            joinedload(PromptVersion.variables),
            joinedload(PromptVersion.messages)
        ]
        query = session.query(PromptVersion).filter(*filters).options(*options)
        prompt_version = query.first()

        if not prompt_version and version_name == 'latest':
            filters = [PromptVersion.prompt_id == prompt_id, ]

            query = (
                session.query(PromptVersion)
                .filter(*filters)
                .options(*options)
                .order_by(PromptVersion.created_at.desc())
            )
            prompt_version = query.first()

        if not prompt_version:
            return {
                'ok': False,
                'msg': f'No prompt found with id \'{prompt_id}\' or no version \'{version_name}\''
            }

        result = PromptDetailModel.from_orm(prompt_version.prompt)
        result.version_details = PromptVersionDetailModel.from_orm(prompt_version)
    return {'ok': True, 'data': result.json()}


def get_published_prompt_details(project_id: int, prompt_id: int, version_name: str = None) -> dict:
    with db.with_project_schema_session(project_id) as session:
        filters = [
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.status == PromptVersionStatus.published
        ]
        if version_name:
            filters.append(PromptVersion.name == version_name)

        query = (
            session.query(PromptVersion)
            .filter(*filters)
            .options(
                joinedload(PromptVersion.prompt).options(joinedload(Prompt.versions)),
                joinedload(PromptVersion.variables),
                joinedload(PromptVersion.messages)
            )
            .order_by(PromptVersion.created_at.desc())
        )
        prompt_version = query.first()

        if not prompt_version:
            return {
                'ok': False,
                'msg': f'No prompt found with id \'{prompt_id}\' or no public version'
            }
        result = PublishedPromptDetailModel.from_orm(prompt_version.prompt)
        result.version_details = PromptVersionDetailModel.from_orm(prompt_version)
        result.get_likes(project_id)
        result.check_is_liked(project_id)

    return {'ok': True, 'data': result.json()}


def list_prompts_api(
        project_id: int,
        tags: str | list | None = None,
        author_id: int | None = None,
        statuses: str | list | None = None,
        q: str | None = None,
        limit: int = 10,
        offset: int = 0,
        sort_by: str = 'created_at',
        sort_order: Literal['asc', 'desc'] = 'desc',
        my_liked: bool = False,
        trend_start_period: str | None = None,
        trend_end_period: str | None = None,
        with_likes: bool = True,
        collection: Optional[dict[str, int]] = None,
        search_data: Optional[dict] = None
):
    filters = []
    if tags:
        if isinstance(tags, str):
            tags = tags.split(',')
        filters.append(Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags))))

    if author_id:
        filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))

    if statuses:
        if isinstance(statuses, str):
            statuses = statuses.split(',')
        filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))

    # Search parameters
    if q:
        filters.append(
            or_(
                Prompt.name.ilike(f"%{q}%"),
                Prompt.description.ilike(f"%{q}%")
            )
        )

    if search_data:
        searches = []
        for keyword in search_data.get('keywords', []):
            searches.append(
                or_(
                    Prompt.name.ilike(f"%{keyword}%"),
                    Prompt.description.ilike(f"%{keyword}%")
                )
            )
        if tag_ids := search_data.get('tag_ids'):
            searches.append(Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tag_ids))))     
        filters.append(or_(*searches))


    if collection and collection.get('id') and collection.get('owner_id'):
        collection_value = {
            "id": collection['id'],
            "owner_id": collection['owner_id']
        }
        filters.append(Prompt.collections.contains([collection_value]))

    trend_period = None
    if trend_start_period:
        if isinstance(trend_start_period, str):
            trend_start_period = datetime.strptime(trend_start_period, "%Y-%m-%dT%H:%M:%S")
        if not trend_end_period:
            trend_end_period = datetime.utcnow()
        if isinstance(trend_end_period, str):
            trend_end_period = datetime.strptime(trend_end_period, "%Y-%m-%dT%H:%M:%S")
        trend_period = (trend_start_period, trend_end_period)

    # list prompts
    total, prompts = list_prompts(
        project_id=project_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        my_liked=my_liked,
        trend_period=trend_period,
        with_likes=with_likes,
        filters=filters,
    )
    if search_data:
        fire_searched_event(project_id, search_data)

    return {
        'total': total,
        'prompts': prompts,
    }


def fire_searched_event(project_id: int, search_data: dict):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        "prompt_lib_search_conducted", 
        {
            "project_id": project_id,
            "search_data": search_data,
        }
    )
