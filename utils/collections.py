import json
from collections import defaultdict
from typing import List
from tools import auth, db, VaultClient, rpc_tools
import copy

from pylon.core.tools import log
from ..models.enums.all import CollectionPatchOperations
from ..models.all import Collection, Prompt
from ..models.pd.collections import (
    CollectionDetailModel,
    CollectionModel,
    MultiplePromptModel,
    PromptIds,
    CollectionPatchModel,
)


class PromptInaccessableError(Exception):
    "Raised when prompt in project for which user doesn't have permission"

    def __init__(self, message):
        self.message = message


class PromptDoesntExist(Exception):
    "Raised when prompt doesn't exist"
    def __init__(self, message):
        self.message = message


def check_prompts_addability(context, owner_id: int, user_id: int):
    membership_check = context.rpc_manager.call.admin_check_user_in_project
    secrets = VaultClient().get_all_secrets()
    ai_project_id = secrets.get("ai_project_id")
    return (
        ai_project_id and int(ai_project_id) == int(owner_id)
    ) or membership_check(owner_id, user_id)


def list_collections(project_id: int, args=None):
    if args is None:
        args = {}
    # Pagination parameters
    limit = args.get("limit", default=10, type=int)
    offset = args.get("offset", default=0, type=int)

    # Sorting parameters
    sort_by = args.get("sort_by", default="id")
    sort_order = args.get("sort_order", default="desc")

    with db.with_project_schema_session(project_id) as session:
        query: List[Collection] = session.query(Collection)

        # Apply sorting
        if sort_order.lower() == "asc":
            query = query.order_by(getattr(Collection, sort_by))
        else:
            query = query.order_by(getattr(Collection, sort_by).desc())

        total = query.count()

        # Apply limit and offset for pagination
        query = query.limit(limit).offset(offset)
        prompts = query.all()
    return total, prompts


def delete_collection(project_id: int, collection_id: int):
    with db.with_project_schema_session(project_id) as session:
        if prompt := session.query(Collection).get(collection_id):
            session.delete(prompt)
            session.commit()
            return True
    return False


def update_collection(context, project_id: int, collection_id: int, data: dict):
    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            for prompt in data.get("prompts", []):
                owner_id = prompt["owner_id"]
                if not check_prompts_addability(
                    context, owner_id, collection.author_id
                ):
                    raise PromptInaccessableError(
                        f"User doesn't have access to project '{owner_id}'"
                    )

            for field, value in data.items():
                if hasattr(collection, field):
                    setattr(collection, field, value)

            session.commit()
            return get_detail_collection(collection)
        return None


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
    collection.author = auth.get_user(user_id=collection.author_id)
    result = json.loads(collection.json(exclude={"author_id"}))

    prompts = []
    actual_prompt_ids = {}
    for project_id, ids in transformed_prompts.items():
        with db.with_project_schema_session(project_id) as session:
            project_prompts = (
                session.query(Prompt).filter(Prompt.id.in_(ids)).all()
            )
            prompts.extend(
                json.loads(MultiplePromptModel(prompts=project_prompts).json())[
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


def create_collection(context, project_id: int, data):
    collection: CollectionModel = CollectionModel.parse_obj(data)
    user_id = data["author_id"]

    for prompt in collection.prompts:
        owner_id = prompt.owner_id
        if not check_prompts_addability(context, owner_id, user_id):
            raise PromptInaccessableError(
                f"User doesn't have access to project '{owner_id}'"
            )

    with db.with_project_schema_session(project_id) as session:
        collection = Collection(**collection.dict())
        session.add(collection)
        session.commit()
        return get_detail_collection(collection)


def add_prompt_to_collection(collection, prompt_data: PromptIds):
    prompts_list: List = copy.deepcopy(collection.prompts)
    prompts_list.append(json.loads(prompt_data.json()))
    collection.prompts = prompts_list
    return get_detail_collection(collection)


def remove_prompt_from_collection(collection, prompt_data: PromptIds):
    prompts_list = [
        copy.deepcopy(prompt) for prompt in collection.prompts 
        if not(int(prompt['owner_id']) == prompt_data.owner_id and \
            int(prompt['id']) == prompt_data.id)
    ]
    collection.prompts = prompts_list
    return get_detail_collection(collection)


def patch_collection(context, project_id, collection_id, data: CollectionPatchModel):
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
            if not check_prompts_addability(context, prompt_data.owner_id, collection.author_id):
                raise PromptInaccessableError(
                    f"User doesn't have access to project '{prompt_data.owner_id}'"
                )
            
            result = op_map[data.operation](collection, prompt_data)
            session.commit()
            return result
        return None