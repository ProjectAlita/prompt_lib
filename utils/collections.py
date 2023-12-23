import json
from collections import defaultdict
from typing import List

from werkzeug.datastructures import MultiDict

from sqlalchemy.orm import joinedload
from tools import auth, db, VaultClient, rpc_tools
import copy
from sqlalchemy import or_, and_
from sqlalchemy.sql import exists

from pylon.core.tools import log

from .utils import get_authors_data
from ..models.enums.all import CollectionPatchOperations, CollectionStatus
from ..models.all import Collection, Prompt, PromptVersion
from ..models.pd.base import PromptTagBaseModel
from ..models.pd.list import MultiplePromptListModel
from ..models.pd.collections import (
    CollectionDetailModel,
    CollectionModel,
    PromptIds,
    CollectionPatchModel,
)
from .publish_utils import get_public_project_id


class PromptInaccessableError(Exception):
    "Raised when prompt in project for which user doesn't have permission"

    def __init__(self, message):
        self.message = message


class PromptDoesntExist(Exception):
    "Raised when prompt doesn't exist"
    def __init__(self, message):
        self.message = message


def check_prompts_addability(owner_id: int, user_id: int):
    membership_check = rpc_tools.RpcMixin().rpc.call.admin_check_user_in_project
    secrets = VaultClient().get_all_secrets()
    ai_project_id = secrets.get("ai_project_id")
    return (
        ai_project_id and int(ai_project_id) == int(owner_id)
    ) or membership_check(owner_id, user_id)


def list_collections(project_id: int, args:  MultiDict[str, str] | dict | None = None):
    if args is None:
        args = dict()

    if isinstance(args, dict):
        # Pagination parameters
        limit = args.get("limit", 10)
        offset = args.get("offset", 0)

        # Sorting parameters
        sort_by = args.get("sort_by", "id")
        sort_order = args.get("sort_order", "desc")

        # Search query filters
        search = args.get('query')
    else:
        # Pagination parameters
        limit = args.get("limit", default=10, type=int)
        offset = args.get("offset", default=0, type=int)

        # Sorting parameters
        sort_by = args.get("sort_by", default="id")
        sort_order = args.get("sort_order", default="desc")

        # Search query filters
        search = args.get("query")

    # filtering
    filters = []
    if author_id := args.get('author_id'):
        filters.append(Collection.author_id==author_id)

    if status := args.get('status'):
        filters.append(Collection.status == status)

    with db.with_project_schema_session(project_id) as session:
        query = session.query(Collection)

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
        if sort_order.lower() == "asc":
            query = query.order_by(getattr(Collection, sort_by))
        else:
            query = query.order_by(getattr(Collection, sort_by).desc())

        total = query.count()

        # Apply limit and offset for pagination
        query = query.limit(limit).offset(offset)
        prompts: List[Collection] = query.all()
    return total, prompts


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


def get_collection(project_id: int, collection_id: int):
    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            return get_detail_collection(collection)
        return None


def get_detail_collection(collection: Collection):
    transformed_prompts = defaultdict(list)
    for prompt in collection.prompts:
        project = prompt["owner_id"]
        transformed_prompts[project].append(prompt["id"])

    data = collection.to_json()
    data.pop('prompts')

    collection = CollectionDetailModel(**data)
    users = get_authors_data([collection.author_id])
    user_map = {i['id']: i for i in users}
    # collection.author = auth.get_user(user_id=collection.author_id)
    collection.author = user_map.get(collection.author_id)
    result = json.loads(collection.json(exclude={"author_id"}))

    prompts = []
    actual_prompt_ids = {}
    for project_id, ids in transformed_prompts.items():
        with db.with_project_schema_session(project_id) as session:
            project_prompts = (
                session.query(Prompt).filter(Prompt.id.in_(ids)).all()
            )
            prompts.extend(
                json.loads(MultiplePromptListModel(prompts=project_prompts).json())[
                    "prompts"
                ]
            )
            actual_prompt_ids[project_id] = [prompt['id'] for prompt in prompts]
    result["prompts"] = prompts
    prune_stale_prompts(collection, transformed_prompts, actual_prompt_ids)
    return result


def prune_stale_prompts(collection, collection_prompts: dict, actual_prompts: dict):
    payload = {
        "existing_prompts": actual_prompts,
        "all_prompts": collection_prompts,
        "collection_data": {
            'owner_id': collection.owner_id,
            'id': collection.id
        }
    }
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        "prune_collection_prompts", payload
    )


def create_collection(project_id: int, data):
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

                for version in prompt.versions:
                    for tag in version.tags:
                        tags[tag.name] = PromptTagBaseModel.from_orm(tag)

    return list(tags.values())

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
            prompt_ids = session.query(Prompt.id).filter(
                or_(
                    *[ 
                        and_(
                            Prompt.shared_id==data['id'],
                            Prompt.shared_owner_id==data['owner_id']
                        ) for data in private_prompt_ids
                    ]
                )
            ).all()
        result = [{"id": prompt_id[0], "owner_id": self._public_id} for prompt_id in prompt_ids]
        return result


    def _set_status(self, project_id, collection_id, status: CollectionStatus):
        with db.with_project_schema_session(project_id) as session:
            collection = session.query(Collection).get(collection_id)
            #
            if not collection:
                return
            #
            collection.status = status
            session.commit()

    def set_statuses_published(self, public_collection_data: Collection):
        # set public collection published
        collection_id = public_collection_data.id
        self._set_status(self._public_id, collection_id, CollectionStatus.published)

        # set private collection published
        self._set_status(self._project_id, self._collection_id, CollectionStatus.published)

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
        result = get_detail_collection(new_collection)
        self.set_statuses_published(new_collection)
        return {
            "ok": True,
            "new_collection": result
        }


def unpublish(current_user_id, collection_id):
    public_id = get_public_project_id()
    with db.with_project_schema_session(public_id) as session:
        collection = session.query(Collection).get(collection_id)
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
        return {"ok": True, "msg": "Successfully unpublished"}