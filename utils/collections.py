import json
from collections import defaultdict
from typing import List
from sqlalchemy.orm import joinedload
from tools import auth, db, VaultClient

from pylon.core.tools import log
from ..models.all import Collection, PromptVersion
from ..models.pd.collections import (
    CollectionDetailModel,
    CollectionModel,
    MultiplePromptVersionModel,
)


class PromptInaccessableError(Exception):
    "Raised when prompt in project for which user doesn't have permission"


def check_prompts_addability(context, project_id: int, user_id: int):
    membership_check = context.rpc_manager.call.admin_check_user_in_project
    secrets = VaultClient().get_all_secrets()
    ai_project_id = secrets.get("ai_project_id")
    return (
        ai_project_id and int(ai_project_id) == int(project_id)
    ) or membership_check(project_id, user_id)


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
    # new_prompt_ids = data.pop("prompts", None)
    # user_id = data["author_id"]

    # for prompt in data.get("prompts", []):
    #     project_id = prompt["project_id"]
    #     if not check_prompts_addability(context, project_id, user_id):
    #         raise PromptInaccessableError(
    #             f"User doesn't have access to project '{project_id}'"
    #         )

    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            # if new_prompt_ids:
            #     collection.prompts = (
            #         session.query(PromptVersion)
            #         .filter(PromptVersion.id.in_(new_prompt_ids))
            #         .all()
            #     )

            for prompt in data.get("prompts", []):
                project_id = prompt["project_id"]
                if not check_prompts_addability(
                    context, project_id, collection.author_id
                ):
                    raise PromptInaccessableError(
                        f"User doesn't have access to project '{project_id}'"
                    )

            for field, value in data.items():
                if hasattr(collection, field):
                    setattr(collection, field, value)

            session.commit()
            # result = CollectionDetailModel.from_orm(collection)
            # result.author = auth.get_user(user_id=result.author_id)
            # return json.loads(result.json())
            return get_detail_collection(collection)
        return None


def get_collection(project_id: int, collection_id: int):
    with db.with_project_schema_session(project_id) as session:
        if collection := session.query(Collection).get(collection_id):
            log.info(collection)
            return get_detail_collection(collection)
        return None


def get_detail_collection(collection: Collection):
    transformed_prompts = defaultdict(list)
    for prompt in collection.prompts:
        project = prompt["project_id"]
        transformed_prompts[project].append(prompt["id"])

    collection = CollectionDetailModel(
        id=collection.id,
        prompts=[],
        name=collection.name,
        owner_id=collection.owner_id,
        author_id=collection.author_id,
    )
    collection.author = auth.get_user(user_id=collection.author_id)
    result = json.loads(collection.json(exclude={"author_id"}))

    prompts = []
    for project_id, ids in transformed_prompts.items():
        with db.with_project_schema_session(project_id) as session:
            project_prompts = (
                session.query(PromptVersion).filter(PromptVersion.id.in_(ids)).all()
            )
            prompts.extend(
                json.loads(MultiplePromptVersionModel(prompts=project_prompts).json())[
                    "prompts"
                ]
            )
    result["prompts"] = prompts
    return result


def create_collection(context, project_id: int, data):
    collection: CollectionModel = CollectionModel.parse_obj(data)
    user_id = data["author_id"]

    for prompt in collection.prompts:
        project_id = prompt.project_id
        if not check_prompts_addability(context, project_id, user_id):
            raise PromptInaccessableError(
                f"User doesn't have access to project '{project_id}'"
            )

    with db.with_project_schema_session(project_id) as session:
        # prompts = (
        #     session.query(PromptVersion)
        #     .filter(PromptVersion.id.in_(collection.prompts))
        #     .all()
        # )
        # collection.prompts = prompts
        collection = Collection(**collection.dict())
        session.add(collection)
        session.commit()

        return get_detail_collection(collection)
