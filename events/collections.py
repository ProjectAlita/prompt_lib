from pylon.core.tools import log, web

from tools import db
from ..models.all import Collection
from copy import deepcopy

class Event:
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