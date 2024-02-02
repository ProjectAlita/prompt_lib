import json
import copy
from datetime import datetime
from collections import defaultdict
from typing import List, Union, Dict
from werkzeug.datastructures import MultiDict
from flask import request
from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import exists

from tools import db, VaultClient, rpc_tools
# from pylon.core.tools import log

from .like_utils import add_likes, add_my_liked, add_trending_likes
from .prompt_utils import set_columns_as_attrs
from .utils import get_author_data, get_authors_data, add_public_project_id
from ..models.enums.all import CollectionPatchOperations, CollectionStatus, PromptVersionStatus
from ..models.all import Collection, Prompt, PromptVersion, PromptTag
from ..models.pd.base import PromptTagBaseModel
from ..models.pd.list import PublishedPromptListModel, PromptListModel
from ..models.pd.collections import (
    CollectionDetailModel,
    CollectionModel,
    PromptIds,
    CollectionPatchModel,
    PublishedCollectionDetailModel, CollectionListModel, 
    CollectionShortDetailModel,
)
from .publish_utils import get_public_project_id
from .expceptions import (
    PromptInaccessableError,
    PromptDoesntExist,
    PromptAlreadyInCollectionError,
    NotFound
)


def check_prompts_addability(owner_id: int, user_id: int):
    membership_check = rpc_tools.RpcMixin().rpc.call.admin_check_user_in_project
    secrets = VaultClient().get_all_secrets()
    ai_project_id = secrets.get("ai_project_id")
    return (
        ai_project_id and int(ai_project_id) == int(owner_id)
    ) or membership_check(owner_id, user_id)


def get_prompts_for_collection(collection_prompts: List[Dict[str, int]], only_public: bool = False) -> list:
    prompts = []
    filters = []
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 10, type=int)
    trend_period = request.args.get("trending_period")
    my_liked = request.args.get('my_liked', False)

    if tags := request.args.get('tags'):
        # # Filtering parameters
        if isinstance(tags, str):
            tags = tags.split(',')
        filters.append(Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags))))

    if author_id := request.args.get('author_id'):
        filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))

    if statuses := request.args.get('statuses'):
        statuses = statuses.split(',')
        filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))

    # Search parameters
    if search := request.args.get('query'):
        filters.append(
            or_(
                Prompt.name.ilike(f"%{search}%"),
                Prompt.description.ilike(f"%{search}%")
            )
        )

    if only_public:
        filters.append(
            Prompt.versions.any(PromptVersion.status == PromptVersionStatus.published)
        )

    grouped_prompts = group_by_project_id(collection_prompts)
    for project_id, ids in grouped_prompts.items():
        with db.with_project_schema_session(project_id) as session:
            prompt_query = session.query(Prompt).filter(Prompt.id.in_(ids), *filters)
            extra_columns = []

            if only_public:
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

                prompt_query, new_columns = add_my_liked(
                    original_query=prompt_query,
                    project_id=project_id,
                    entity_name='prompt',
                    filter_results=my_liked
                )
                extra_columns.extend(new_columns)

                # prompt_query = add_likes(prompt_query, project_id, 'prompt')
            q_result = prompt_query.all()
            project_prompts = list(set_columns_as_attrs(q_result, extra_columns))

            # user_map
            author_ids = set()
            for prompt in project_prompts:
                # prompt = prompt[0] if only_public else prompt
                for version in prompt.versions:
                    author_ids.add(version.author_id)
            users = get_authors_data(list(author_ids))
            user_map = {user['id']: user for user in users}

            for prompt in project_prompts:
                if only_public:
                    prompt = PublishedPromptListModel.from_orm(prompt)
                else:
                    prompt = PromptListModel.from_orm(prompt)
                prompt.set_authors(user_map)
                prompts.append(json.loads(prompt.json()))
                # if only_public:
                #     prompts.append(json.loads(prompt.json()))
                # else:
                #     prompts.append()
                #     prompts.extend(
                #         json.loads(MultiplePromptListModel(prompts=project_prompts).json())[
                #             "prompts"
                #         ]
                #     )
    
    prompts = prompts[offset:limit+offset]
    return prompts


def get_filter_collection_by_tags_condition(project_id: int, tags: List[int], session=None):
    if session is None:
        session = db.get_project_schema_session(project_id)

    prompt_ids = session.query(Prompt.id).filter(
        Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags)))
    ).all()

    if not prompt_ids:
        raise NotFound("No prompt with given tags found")

    prompt_filters = []
    for id_ in prompt_ids:
        prompt_value = {
            "owner_id": project_id,
            "id": id_[0]
        }
        prompt_filters.append(Collection.prompts.contains([prompt_value]))
    
    session.close()
    return or_(*prompt_filters)



def list_collections(
        project_id: int,
        args:  MultiDict[str, str] | dict | None = None,
        with_likes: bool = True,
        my_liked: bool = False
        ):

    if my_liked:
        my_liked = with_likes

    if args is None:
        args = dict()

    if type(args) == dict:
        # Pagination parameters
        limit = args.get("limit", 10)
        offset = args.get("offset", 0)

        # Sorting parameters
        sort_by = args.get("sort_by", "id")
        sort_order = args.get("sort_order", "desc")

        # Search query filters
        search = args.get('query')

        # trend period
        trend_start_period = args.get('trend_start_period')
        trend_end_period = args.get('trend_end_period')
    else:
        # Pagination parameters
        limit = args.get("limit", default=10, type=int)
        offset = args.get("offset", default=0, type=int)

        # Sorting parameters
        sort_by = args.get("sort_by", default="id")
        sort_order = args.get("sort_order", default="desc")

        # Search query filters
        search = args.get("query")

        # trend period
        trend_start_period = args.get('trend_start_period')
        trend_end_period = args.get('trend_end_period')

    trend_period = None
    if trend_start_period:
        trend_end_period = datetime.now() if not trend_end_period \
            else datetime.strptime(trend_end_period, "%Y-%m-%dT%H:%M:%S")
        trend_start_period = datetime.strptime(trend_start_period, "%Y-%m-%dT%H:%M:%S")
        trend_period = (trend_start_period, trend_end_period)

    # filtering
    filters = []
    if author_id := args.get('author_id'):
        filters.append(Collection.author_id==author_id)

    if statuses := args.get('statuses'):
        if isinstance(statuses, str):
            statuses = statuses.split(',')
        filters.append(Collection.status.in_(statuses))

    with db.with_project_schema_session(project_id) as session:
        if tags := args.get('tags'):
            # tag filtering
            if isinstance(tags, str):
                tags = tags.split(',')
            try:
                condition = get_filter_collection_by_tags_condition(project_id, tags)
            except NotFound:
                return 0, []
            filters.append(condition)

        query = session.query(Collection)
        extra_columns = []
        if with_likes:
            query, new_columns = add_likes(
                original_query=query,
                project_id=project_id,
                entity_name='collection',
            )
            extra_columns.extend(new_columns)
        if trend_period:
            query, new_columns = add_trending_likes(
                original_query=query,
                project_id=project_id,
                entity_name='collection',
                trend_period=trend_period,
                filter_results=True
            )
            extra_columns.extend(new_columns)
        # if my_liked:
        query, new_columns = add_my_liked(
            original_query=query,
            project_id=project_id,
            entity_name='collection',
            filter_results=my_liked
        )
        extra_columns.extend(new_columns)

        if search:
            query = query.filter(
                or_(
                    Collection.name.ilike(f"%{search}%"),
                    Collection.description.ilike(f"%{search}%")
                )
            )

        if filters:
            query = query.filter(*filters)

        # Apply sorting
        if not trend_period:
            if sort_order.lower() == "asc":
                query = query.order_by(getattr(Collection, sort_by, sort_by))
            else:
                query = query.order_by(desc(getattr(Collection, sort_by, sort_by)))

        total = query.count()

        # Apply limit and offset for pagination
        query = query.limit(limit).offset(offset)


        q_result: Union[List[tuple[Collection, int, int]], List[Collection]] = query.all()

        # if with_likes:
        #     collections_with_likes = []
        #     for collection, likes, is_liked, *other in collections:
        #         collection.likes = likes
        #         collection.is_liked = is_liked
        #         if other:
        #             collection.trending_likes = other[0]
        #         collections_with_likes.append(collection)
        #     collections = collections_with_likes

    return total, list(set_columns_as_attrs(q_result, extra_columns))


def delete_collection(project_id: int, collection_id: int):
    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            collection_data = collection.to_json()
            session.delete(collection)
            session.commit()
            fire_collection_deleted_event(collection_data)
            return True
    return False

def fire_collection_deleted_event(collection_data: dict):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        'prompt_lib_collection_deleted', collection_data
    )


def fire_collection_prompt_unpublished(collection_data):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        "prompt_lib_collection_unpublished", {
            "private_id": collection_data['shared_id'],
            "private_owner_id": collection_data['shared_owner_id']
        }
    )


def update_collection(project_id: int, collection_id: int, data: dict):
    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            for prompt in data.get("prompts", []):
                owner_id = prompt["owner_id"]
                if not check_prompts_addability(owner_id, collection.author_id):
                    raise PromptInaccessableError(
                        f"User doesn't have access to project '{owner_id}'"
                    )

            # snapshoting old state
            old_state = collection.to_json()

            for field, value in data.items():
                if hasattr(collection, field):
                    setattr(collection, field, value)
            session.commit()

            fire_collection_updated_event(old_state, data)
            return get_detail_collection(collection)
        return None


def fire_collection_updated_event(old_state: dict, collection_payload: dict):
    if 'prompts' not in collection_payload:
        return

    # old state map
    old_state_tuple_set = set()
    for prompt in old_state['prompts']:
        old_state_tuple_set.add((prompt['owner_id'], prompt['id']))

    # new state map
    new_state_tuple_set = set()
    for prompt in collection_payload['prompts']:
        new_state_tuple_set.add((prompt['owner_id'], prompt['id']))

    removed_prompts = old_state_tuple_set - new_state_tuple_set
    added_prompts = new_state_tuple_set - old_state_tuple_set

    rpc_tools.EventManagerMixin().event_manager.fire_event(
        'prompt_lib_collection_updated', {
            "removed_prompts": removed_prompts,
            "added_prompts": added_prompts,
            "collection_data": {
                "owner_id": old_state['owner_id'],
                "id": old_state['id']
            }
        }
    )


def get_collection(project_id: int, collection_id: int, only_public: bool = False):
    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            return get_detail_collection(collection, only_public)
        return None


def get_detail_collection(collection: Collection, only_public: bool = False):
    data = collection.to_json()
    project_id = data['owner_id']
    data.pop('prompts')

    collection_model = PublishedCollectionDetailModel if only_public \
        else CollectionDetailModel

    collection_data = collection_model(**data)
    collection_data.author = get_author_data(collection.author_id)

    if only_public:
        collection_data.get_likes(project_id)
        collection_data.check_is_liked(project_id)

    result = json.loads(collection_data.json(exclude={"author_id"}))
    prompts = get_prompts_for_collection(collection.prompts, only_public=only_public)
    result["prompts"] = {"total": len(collection.prompts), "rows": prompts}
    return result


def create_collection(project_id: int, data, fire_event=True):
    collection: CollectionModel = CollectionModel.parse_obj(data)
    user_id = data["author_id"]

    for prompt in collection.prompts:
        owner_id = prompt.owner_id
        if not check_prompts_addability(owner_id, user_id):
            raise PromptInaccessableError(
                f"User doesn't have access to project '{owner_id}'"
            )

    with db.with_project_schema_session(project_id) as session:
        collection = Collection(**collection.dict())
        session.add(collection)
        session.commit()
        if fire_event:
            fire_collection_created_event(collection.to_json())
        return collection


def fire_collection_created_event(collection_data: dict):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        'prompt_lib_collection_added', collection_data
    )

def add_prompt_to_collection(collection, prompt_data: PromptIds, return_data=True):
    prompts_list: List = copy.deepcopy(collection.prompts)
    prompts_list.append(json.loads(prompt_data.json()))
    collection.prompts = prompts_list
    if return_data:
        return get_detail_collection(collection)


def remove_prompt_from_collection(collection, prompt_data: PromptIds, return_data=True):
    prompts_list = [
        copy.deepcopy(prompt) for prompt in collection.prompts
        if not(int(prompt['owner_id']) == prompt_data.owner_id and \
            int(prompt['id']) == prompt_data.id)
    ]
    collection.prompts = prompts_list
    if return_data:
        return get_detail_collection(collection)


def fire_patch_collection_event(collection_data, operartion, prompt_data):
    if operartion == CollectionPatchOperations.add:
        removed_prompts = tuple()
        added_prompts = [(prompt_data['owner_id'], prompt_data['id'])]
    else:
        added_prompts = tuple()
        removed_prompts = [(prompt_data['owner_id'], prompt_data['id'])]

    rpc_tools.EventManagerMixin().event_manager.fire_event(
        'prompt_lib_collection_updated', {
            "removed_prompts": removed_prompts,
            "added_prompts": added_prompts,
            "collection_data": {
                "owner_id": collection_data['owner_id'],
                "id": collection_data['id']
            }
        }
    )

def patch_collection(project_id, collection_id, data: CollectionPatchModel):
    op_map = {
        CollectionPatchOperations.add: add_prompt_to_collection,
        CollectionPatchOperations.remove: remove_prompt_from_collection
    }
    prompt_data = data.prompt

    with db.with_project_schema_session(prompt_data.owner_id) as prompt_session:
        prompt = prompt_session.query(Prompt).filter_by(id=prompt_data.id).first()
        if not prompt:
            raise PromptDoesntExist(
                f"Prompt '{prompt_data.id}' in project '{prompt_data.owner_id}' doesn't exist"
            )


    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            if not check_prompts_addability(prompt_data.owner_id, collection.author_id):
                raise PromptInaccessableError(
                    f"User doesn't have access to project '{prompt_data.owner_id}'"
                )

            # todo: check target collection id is not equal to public project id
            # if collection.owner_id != prompt.owner_id:
            #
            if data.operation == CollectionPatchOperations.add and get_include_prompt_flag(
                collection=CollectionListModel.from_orm(collection),
                prompt_id=prompt.id,
                prompt_owner_id=prompt.owner_id,
            ):
                raise PromptAlreadyInCollectionError('Already in collection')

            # with db.with_project_schema_session(project_id) as session:
            #     q = session.query(Prompt).filter(
            #     ) todo: add personal prompt if public replica is being added

            result = op_map[data.operation](collection, prompt_data)
            collection_data = collection.to_json()
            session.commit()
            fire_patch_collection_event(
                collection_data, data.operation, prompt_data.dict()
            )
            return result
        return None

def get_collection_tags(prompts: List[dict]) -> list:
    tags = dict()

    prompts_data = defaultdict(list)
    for prompt_data in prompts:
        prompts_data[prompt_data['owner_id']].append(prompt_data['id'])

    for project_id, prompt_ids in prompts_data.items():
        with db.with_project_schema_session(project_id) as session:
            for prompt_id in prompt_ids:
                query = (
                    session.query(Prompt)
                    .options(
                        joinedload(Prompt.versions).joinedload(PromptVersion.tags)
                    )
                )
                prompt = query.get(prompt_id)

                if not prompt:
                    continue

                for version in prompt.versions:
                    for tag in version.tags:
                        tags[tag.name] = PromptTagBaseModel.from_orm(tag)

    return list(tags.values())


def fire_public_collection_status_change_event(shared_owner_id, shared_id, status):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        'prompt_public_collection_status_change', {
        'private_project_id': shared_owner_id,
        'private_collection_id': shared_id,
        'status': status
    })

class CollectionPublishing:
    def __init__(self, project_id: int, collection_id: int):
        self._project_id = project_id
        self._collection_id = collection_id
        self._public_id = get_public_project_id()

    def check_already_published(self):
        with db.with_project_schema_session(self._public_id) as session:
            exist_query = (
                session.query(exists().where(and_(
                    Collection.shared_id==self._collection_id,
                    Collection.shared_owner_id==self._project_id,
                )))
            ).scalar()
            return exist_query

    def get_public_prompts_of_collection(self, private_prompt_ids: List[dict]):
        with db.with_project_schema_session(self._public_id) as session:
            if not private_prompt_ids:
                raise Exception("Collection doesn't contain public prompts")
            
            public_prompts = filter(lambda x: x['owner_id']==self._public_id, private_prompt_ids)
            private_prompts = filter(lambda x: x['owner_id']!=self._public_id, private_prompt_ids)

            prompt_ids = session.query(Prompt.id).filter(
                or_(
                    *[
                        and_(
                            Prompt.shared_id==data['id'],
                            Prompt.shared_owner_id==data['owner_id']
                        ) for data in private_prompts
                    ],
                    *[
                        and_(
                            Prompt.id==data['id'],
                        ) for data in public_prompts
                    ]
                ),
                Prompt.versions.any(PromptVersion.status == PromptVersionStatus.published)
            ).all()
            
            if not prompt_ids:
                raise Exception("Collection doesn't contain public prompts")
            
        result = [{"id": prompt_id[0], "owner_id": self._public_id} for prompt_id in prompt_ids]
        return result

    @staticmethod
    def set_status(project_id, collection_id, status: CollectionStatus, session=None):
        if session is None:
            session = db.get_project_schema_session(project_id)

        collection = session.query(Collection).get(collection_id)
        #
        if not collection:
            return
        #
        collection.status = status
        session.commit()
        session.close
        
        if session:
            return collection

    @staticmethod
    def approve(project_id, collection_id):
        # changing the status of collection
        with db.with_project_schema_session(project_id) as session:
            collection = CollectionPublishing.set_status(
                    project_id, collection_id, CollectionStatus.published, session
            )
            #
            fire_public_collection_status_change_event(
                collection.shared_owner_id,
                collection.shared_id,
                CollectionStatus.published
            )
            collection_model = CollectionShortDetailModel.from_orm(collection)
        return {"ok": True, "result": json.loads(collection_model.json())}


    @staticmethod
    def reject(project_id, collection_id):
        # changing the status of collection
        with db.with_project_schema_session(project_id) as session:
            collection = CollectionPublishing.set_status(
                    project_id, collection_id, CollectionStatus.rejected, session
            )
            #
            fire_public_collection_status_change_event(
                collection.shared_owner_id,
                collection.shared_id,
                CollectionStatus.rejected
            )
            collection_model = CollectionShortDetailModel.from_orm(collection)
        return {"ok": True, "result": json.loads(collection_model.json())}

    def set_statuses(self, public_collection_data: Collection, status: CollectionStatus):
        # set public collection
        collection_id = public_collection_data.id
        self.set_status(self._public_id, collection_id, status)

        # set private collection
        self.set_status(self._project_id, self._collection_id, status)

    def publish(self):
        if self.check_already_published():
            return {
                "ok": False,
                "error": "Already published"
            }

        collection_data = None
        with db.with_project_schema_session(self._project_id) as session:
            collection = session.query(Collection).get(self._collection_id)
            if not collection:
                return {
                    "ok": False,
                    "error": "Collection is not found",
                    "error_code": 404
                }

            collection_data = collection.to_json()
            collection_data['shared_id'] = collection_data.pop('id')
            collection_data['shared_owner_id'] = collection_data.pop('owner_id')
            collection_data['owner_id'] = self._public_id
            collection_data['prompts'] = self.get_public_prompts_of_collection(collection_data['prompts'])

        new_collection = create_collection(self._public_id, collection_data)
        self.set_statuses(new_collection, CollectionStatus.on_moderation)
        new_collection.status = CollectionStatus.on_moderation
        result = get_detail_collection(new_collection)
        return {
            "ok": True,
            "new_collection": result
        }


def unpublish(current_user_id, project_id, collection_id):
    public_id = get_public_project_id()
    with db.with_project_schema_session(public_id) as session:
        collection = session.query(Collection).filter_by(
            shared_id=collection_id,
            shared_owner_id=project_id
        ).first()

        if not collection:
            return {
                "ok": False,
                "error": f"Public collection with id '{collection_id}'",
                "error_code": 404,
            }

        if int(collection.author_id) != int(current_user_id):
            return {
                "ok": False,
                "error": "Current user is not author of the collection",
                "error_code": 403
            }

        if collection.status  == CollectionStatus.draft:
            return {"ok": False, "error": "Collection is not public yet"}

        collection_data = collection.to_json()
        session.delete(collection)
        session.commit()
        fire_collection_deleted_event(collection_data)
        fire_collection_prompt_unpublished(collection_data)
        return {"ok": True, "msg": "Successfully unpublished"}

def group_by_project_id(data, data_type='dict'):
    prompts = defaultdict(set)
    group_field = "owner_id" if not data_type == "tuple" else 0
    data_field = "id" if not data_type == "tuple" else 1
    for entity in data:
        prompts[entity[group_field]].add(entity[data_field])
    return prompts


@add_public_project_id
def get_include_prompt_flag(collection: CollectionListModel, prompt_id: int, prompt_owner_id: int, *,
                                 project_id: int) -> bool:
    public_prompts = []
    for p in collection.prompts:
        p_owner_id = int(p['owner_id'])
        if p_owner_id == prompt_owner_id and \
                int(p['id']) == prompt_id:
            return True
        elif p_owner_id == project_id and \
                prompt_owner_id != project_id:
            # if prompt is public but target collection owner is not public
            public_prompts.append(p)
    else:
        if public_prompts:
            with db.with_project_schema_session(project_id) as session:
                q = session.query(Prompt).filter(
                    Prompt.id.in_([p['id'] for p in public_prompts]),
                    Prompt.shared_owner_id == prompt_owner_id,
                    Prompt.shared_id == prompt_id,
                )
                return bool(q.first())
    return False
