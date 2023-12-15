from pylon.core.tools import log, web
from collections import defaultdict
from tools import db
from ..models.all import Collection, Prompt
from copy import deepcopy


class Event:
    @web.event("prompt_lib_collection_updated")
    def handle_collection_updated(self, context, event, payload: dict):
        added_prompts = payload['added_prompts']
        removed_prompts = payload['removed_prompts']
        collection_data = payload['collection_data']

        # add collection to prompts:
        added_prompts: dict = group_by_project_id(added_prompts, data_type="tuple")
        for project_id, prompt_ids in added_prompts.items():
            with db.with_project_schema_session(project_id) as session:
                add_collection_to_prompts(prompt_ids, collection_data, session)
                session.commit()
        
        # remove collection from prompts
        removed_prompts: dict = group_by_project_id(removed_prompts, data_type="tuple")
        for project_id, prompt_ids in removed_prompts.items():
            with db.with_project_schema_session(project_id) as session:
                delete_collection_from_prompts(prompt_ids, collection_data, session)
                session.commit()


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
        shared_owner_id = payload['shared_owner_id']
        shared_id = payload['shared_id']
        public_prompt_id = payload['public_prompt_id']
        
        # # get all related collections
        # with db.with_project_schema_session(shared_owner_id) as session:
        #     session.query(Collection).filter_by()


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
