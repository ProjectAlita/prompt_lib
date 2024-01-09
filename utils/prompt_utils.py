from json import loads
from typing import List, Optional, Union
from werkzeug.datastructures import MultiDict
from sqlalchemy import func, cast, String, desc, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from tools import db, auth, rpc_tools
from pylon.core.tools import log

from ..models.all import Collection, Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag, PromptVersionTagAssociation
from ..models.pd.legacy.variable import VariableModel
from ..models.pd.update import PromptVersionUpdateModel
from ..models.pd.detail import PromptDetailModel, PromptVersionDetailModel, PublishedPromptDetailModel
from ..models.pd.list import PromptTagListModel
from ..models.enums.all import PromptVersionStatus
from .utils import add_likes_to_query


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


def get_all_ranked_tags(project_id: int, args: MultiDict) -> List[dict]:

    # Args to sort prompt subquery:
    limit = args.get("limit", default=10, type=int)
    offset = args.get("offset", default=0, type=int)
    sort_by = args.get("sort_by", default="id")
    sort_order = args.get("sort_order", default="desc")

    # Filters to sort prompt subquery:
    filters = []
    if author_id := args.get('author_id'):
        filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))
    if statuses := args.get('statuses'):
        statuses = statuses.split(',')
        filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))
    if search := args.get('query'):
        filters.append(
            or_(
                Prompt.name.ilike(f"%{search}%"),
                Prompt.description.ilike(f"%{search}%")
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

            prompt_ids = []
            for collection_prompt in collection_prompts:
                prompts = collection_prompt[0]
                for prompt in prompts:
                    if prompt['owner_id'] == project_id:
                        prompt_ids.append(prompt['id'])
            
            filters.append(Prompt.id.in_(prompt_ids))

        # Prompt subquery
        prompt_query = (
            session.query(Prompt)
            .options(joinedload(Prompt.versions))
        )
        prompt_query = add_likes_to_query(prompt_query, project_id, 'prompt')
        if filters:
            prompt_query = prompt_query.filter(*filters)

        prompt_query = prompt_query.with_entities(Prompt.id)
        prompt_subquery = prompt_query.subquery()

        # Main query
        query = (
            session.query(
                PromptTag.id,
                PromptTag.name,
                cast(PromptTag.data, String),
                func.count(func.distinct(PromptVersion.prompt_id))
            )
            .filter(PromptVersion.prompt_id.in_(prompt_subquery))
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


def list_prompts(project_id: int,
                 limit: int | None = 10, offset: int | None = 0,
                 sort_by: str = 'created_at',
                 sort_order: str = 'desc',
                 filters: Optional[list] = None,
                 with_likes: bool = True) -> tuple:
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

        query = (
            session.query(Prompt)
            .options(joinedload(Prompt.versions).joinedload(PromptVersion.tags))
        )

        if with_likes:
            query = add_likes_to_query(query, project_id, 'prompt')

        if filters:
            query = query.filter(*filters)

        # Apply sorting
        if sort_order.lower() == "asc":
            query = query.order_by(getattr(Prompt, sort_by, sort_by))
        else:
            query = query.order_by(desc(getattr(Prompt, sort_by, sort_by)))

        total = query.count()

        # Apply limit and offset for pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        prompts: Union[List[tuple[Prompt, int, bool]], List[Prompt]] = query.all()

        # log.info(f'prompts: {prompts}')

        if with_likes:
            prompts_with_likes = []
            for prompt, likes, is_liked in prompts:
                prompt.likes = likes
                prompt.is_liked = is_liked
                prompts_with_likes.append(prompt)
            prompts = prompts_with_likes

    return total, prompts


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
            filters = [PromptVersion.prompt_id == prompt_id,]

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
