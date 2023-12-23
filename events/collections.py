from pylon.core.tools import log, web
from collections import defaultdict
from tools import db
from ..models.all import Collection, Prompt
from ..models.enums.all import CollectionPatchOperations
from copy import deepcopy
from ..utils.collections import fire_patch_collection_event, add_prompt_to_collection, remove_prompt_from_collection
from ..utils.publish_utils import get_public_project_id
from sqlalchemy import or_, and_

from ..models.pd.collections import PromptIds


class Event:
    @web.event("prompt_lib_collection_updated")
    def handle_collection_updated(self, context, event, payload: dict):
        added_prompts = payload['added_prompts']
        removed_prompts = payload['removed_prompts']
        collection_data = payload['collection_data']
        public_id = get_public_project_id()

        # add collection to prompts:
        grouped_added_prompts: dict = group_by_project_id(added_prompts, data_type="tuple")
        for project_id, prompt_ids in grouped_added_prompts.items():
            with db.with_project_schema_session(project_id) as session:
                add_collection_to_prompts(prompt_ids, collection_data, session)
                session.commit()
        
        # remove collection from prompts
        grouped_removed_prompts: dict = group_by_project_id(removed_prompts, data_type="tuple")
        for project_id, prompt_ids in grouped_removed_prompts.items():
            with db.with_project_schema_session(project_id) as session:
                delete_collection_from_prompts(prompt_ids, collection_data, session)
                session.commit()
        
        # synchronize private and public collections
        if public_id != collection_data['owner_id']:
            synchronize_collections(
                collection_data, 
                added_prompts, 
                removed_prompts
            )

    @web.event("prompt_lib_collection_deleted")
    def handle_collection_deleted(self, context, event, payload: dict):
        collection_data = payload
        # group by prompt data        
        prompts = group_by_project_id(collection_data['prompts'])
        for owner_id, prompt_ids in prompts.items():
            with db.with_project_schema_session(owner_id) as session:
                delete_collection_from_prompts(prompt_ids, collection_data, session)
                session.commit()


    @web.event("prompt_lib_collection_added")
    def handle_collection_deleted(self, context, event, payload: dict):
        # group by prompt data        
        collection_data = payload
        prompts = group_by_project_id(collection_data['prompts'])
        for owner_id, prompt_ids in prompts.items():
            with db.with_project_schema_session(owner_id) as session:
                add_collection_to_prompts(prompt_ids, collection_data, session)
                session.commit()


    @web.event("prune_collection_prompts")
    def prune_collection_prompts(self, context, event, payload: dict):
        existing_prompts = payload.get('existing_prompts')
        all_prompts = payload.get('all_prompts')
        collection_data = payload.get('collection_data')
        stale_prompts = {}
        for project_id, ids in all_prompts.items():
            collection_ids = set(ids)
            actual_ids = set(existing_prompts[project_id])
            stale_prompts[project_id] = collection_ids - actual_ids
        
        with db.with_project_schema_session(collection_data['owner_id']) as session:
            collection = session.query(Collection).get(collection_data['id'])
            clean_prompts = [
                deepcopy(prompt) for prompt in collection.prompts
                if not prompt['owner_id'] in stale_prompts or \
                    not prompt['id'] in stale_prompts[prompt['owner_id']]
            ]
            collection.prompts = clean_prompts
            session.commit()


    @web.event('prompt_lib_prompt_published')
    def handle_prompt_publishing(self, context, event, payload: dict) -> None:
        prompt_data = payload['prompt_data']
        owner_id = prompt_data['owner_id']
        collections = payload['collections']
        
        with db.with_project_schema_session(owner_id) as session:
            if not collections:
                collections = session.query(Collection).filter(
                    or_(
                        *[
                            and_(
                                Collection.shared_id==collection['id'],
                                Collection.shared_owner_id==collection['owner_id']
                            ) for collection in collections
                        ]
                    )
                ).all()
            else:
                collections = []

            for collection in collections:
                prompts = deepcopy(collection.prompts)
                prompts.append({
                    "owner_id": owner_id,
                    "id": prompt_data['id']
                })
                collection.prompts = prompts
            session.commit()

            for collection in collections:
                fire_patch_collection_event(
                    collection.to_json(), CollectionPatchOperations.add, prompt_data
                )



def group_by_project_id(data, data_type='dict'):
    prompts = defaultdict(list)
    group_field = "owner_id" if not data_type == "tuple" else 0
    data_field = "id" if not data_type == "tuple" else 1
    for entity in data:
        prompts[entity[group_field]].append(entity[data_field])
    return prompts


def delete_collection_from_prompts(prompt_ids: list, collection_data: dict, session):
    col_owner_id = collection_data['owner_id']
    col_id = collection_data['id']
    prompts = session.query(Prompt).filter(Prompt.id.in_(prompt_ids)).all()
    for prompt in prompts:
        new_data = [
            deepcopy(collection) for collection in prompt.collections
            if collection['owner_id'] != col_owner_id or collection['id'] != col_id   
        ]
        prompt.collections = new_data


def add_collection_to_prompts(prompt_ids: list, collection_data: dict, session):
    col_owner_id = collection_data['owner_id']
    col_id = collection_data['id']
    prompts = session.query(Prompt).filter(Prompt.id.in_(prompt_ids)).all()
    for prompt in prompts:
        new_data: list = deepcopy(prompt.collections)
        new_data.append({
            "owner_id": col_owner_id,
            "id": col_id
        })
        prompt.collections = new_data


def synchronize_collections(private_collection_data, added_prompts=[], removed_prompts=[]):
    public_id = get_public_project_id()
    with db.with_project_schema_session(public_id) as session:
        collection = session.query(Collection).filter_by(
            shared_owner_id=private_collection_data['owner_id'],
            shared_id=private_collection_data['id']
        ).first()

        if not collection:
            return
        
        added_prompts = find_public_prompts(added_prompts, session)
        removed_prompts = find_public_prompts(removed_prompts, session)
        
        for prompt in added_prompts:
            prompt = PromptIds(id=prompt.id, owner_id=prompt.owner_id)
            add_prompt_to_collection(collection, prompt)
        
        for prompt in removed_prompts:
            prompt = PromptIds(id=prompt.id, owner_id=prompt.owner_id)
            remove_prompt_from_collection(collection, prompt)
        
        session.commit()


def find_public_prompts(prompts: tuple, session):
    if not prompts:
        return []
    
    return session.query(Prompt).filter(
        or_(
            *[ 
                and_(
                    Prompt.shared_id==prompt[1],
                    Prompt.shared_owner_id==prompt[0]
                ) for prompt in prompts
            ]
        )
    ).all()