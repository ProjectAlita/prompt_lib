from json import loads
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Literal, Generator
from werkzeug.datastructures import MultiDict
from sqlalchemy import cast, String, desc, or_, asc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from tools import db, auth, rpc_tools
from pylon.core.tools import log

from .like_utils import add_likes, add_trending_likes, add_my_liked
from ..models.all import Collection, Prompt, PromptVersion, PromptVariable, PromptMessage, \
    PromptVersionTagAssociation
from ..models.pd.legacy.variable import VariableModel

from ..models.pd.prompt import PromptDetailModel, PublishedPromptDetailModel
from ..models.pd.prompt_version import PromptVersionDetailModel, PromptVersionUpdateModel
from ..models.pd.tag import PromptTagListModel
from ...promptlib_shared.models.all import Tag
from ...promptlib_shared.models.enums.all import PublishStatus
from ...promptlib_shared.utils.utils import get_entities_by_tags


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


def get_prompt_tags(project_id: int, prompt_id: int, args: dict = None) -> List[dict]:
    with db.with_project_schema_session(project_id) as session:
        query = (
            session.query(Tag)
            .join(PromptVersionTagAssociation, PromptVersionTagAssociation.c.tag_id == Tag.id)
            .join(PromptVersion, PromptVersion.id == PromptVersionTagAssociation.c.version_id)
            .filter(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.id)
        )
        filters = list()

        if author_id := args.get('author_id'):
            filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))
        if statuses := args.get('statuses'):
            statuses = statuses.split(',')
            filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))

        if filters:
            query = query.filter(*filters)

        return [PromptTagListModel.from_orm(tag).dict() for tag in query.all()]


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
            existing_tags = session.query(Tag).filter(
                Tag.name.in_({i.name for i in version_data.tags})
            ).all()
            existing_tags_map = {i.name: i for i in existing_tags}
            for tag in version_data.tags:
                prompt_tag = existing_tags_map.get(tag.name, Tag(**tag.dict()))
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
                 limit: int | None = None,
                 offset: int | None = 0,
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
                entity=Prompt,
                sort_by_likes=sort_by_likes,
                sort_order=sort_order
            )
            extra_columns.extend(new_columns)

        if trend_period:
            query, new_columns = add_trending_likes(
                original_query=query,
                project_id=project_id,
                entity=Prompt,
                trend_period=trend_period,
                filter_results=True
            )
            extra_columns.extend(new_columns)
        # if my_liked:
        query, new_columns = add_my_liked(
            original_query=query,
            project_id=project_id,
            entity=Prompt,
            filter_results=my_liked
        )
        extra_columns.extend(new_columns)

        if filters:
            query = query.filter(*filters)

        # Apply sorting
        if not sort_by_likes:
            if sort_by != 'id':
                sort_fn_primary = asc if sort_order.lower() == "asc" else desc
                sort_fn_secondary = asc
                # always ascending for the secondary unique field
                query = query.order_by(
                    sort_fn_primary(getattr(Prompt, sort_by)), sort_fn_secondary(Prompt.id)
                )
            else:
                sort_fn = asc if sort_order.lower() == "asc" else desc
                query = query.order_by(sort_fn(Prompt.id))

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
            PromptVersion.status == PublishStatus.published
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
        limit: int | None = None,
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
            tags = [int(tag) for tag in tags.split(',')]
        prompts_subq = get_entities_by_tags(project_id, tags, Prompt, PromptVersion)
        filters.append(Prompt.id.in_(prompts_subq))
        # filters.append(Prompt.versions.any(PromptVersion.tags.any(Tag.id.in_(tags))))

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

    # if search_data:
    #     for keyword in search_data.get('keywords', []):
    #         filters.append(
    #             or_(
    #                 Prompt.name.ilike(f"%{keyword}%"),
    #                 Prompt.description.ilike(f"%{keyword}%")
    #             )
    #         )
    #     if tag_ids := search_data.get('tag_ids'):
    #         prompt_ids = get_entities_by_tags(project_id, tag_ids, Prompt, PromptVersion)
    #         filters.append(Prompt.id.in_(prompt_ids))


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

    for prompt in prompts:
        try:
            latest_version = prompt.get_latest_version()
            if latest_version:
                prompt.meta = latest_version.meta
            else:
                prompt.meta = {}
        except StopIteration:
            pass

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


def get_prompt_with_versions_dict(project_id: int, prompt_id: int, exclude=None) -> (dict, list):
    with db.with_project_schema_session(project_id) as session:
        prompt = session.query(Prompt).filter(Prompt.id == prompt_id).first()
        if not prompt:
            return None, None
        versions = list()
        for v in prompt.versions:
            v_data = v.to_json(exclude_fields=exclude)
            v_data['tags'] = []
            for i in v.tags:
                v_data['tags'].append(i.to_json())
            versions.append(v_data)
        return prompt.to_json(exclude_fields=exclude), versions


def get_entity_diff(source, target) -> dict:
    all_keys = set(source.keys()).union(set(target.keys()))
    key_diffs = {'modified': {}}
    for key in all_keys:
        if key not in source:
            key_diffs['added'].append({key: target[key]})
        elif key not in target:
            key_diffs['removed'].append({key: source[key]})
        elif source[key] != target[key]:
            key_diffs['modified'][key] = {
                'old_value': source[key],
                'new_value': target[key],
            }
    return key_diffs
