from pylon.core.tools import log, web

from tools import db
from copy import deepcopy
from ..models.all import Collection, Prompt, PromptVersion
from ..models.enums.events import PromptEvents
from ..utils.publish_utils import (
    close_private_version,
    delete_public_version,
    set_status
)

from ..utils.collections import group_by_project_id, delete_entity_from_collections
from ...promptlib_shared.models.enums.all import PublishStatus


class Event:
    @web.event("public_prompt_version_deleted")
    def handler(self, context, event, payload: dict):
        version_data = payload['version_data']
        shared_owner_id = version_data['shared_owner_id']
        with db.with_project_schema_session(shared_owner_id) as session:
            shared_id = version_data['shared_id']
            close_private_version(shared_owner_id, shared_id, session)
            return session.commit()

    @web.event("private_prompt_version_deleted")
    def handler(self, context, event, payload: dict):
        version_data = payload['version_data']
        prompt_data = payload['prompt_data']
        public_id = payload['public_id']
        #
        with db.with_project_schema_session(int(public_id)) as session:
            shared_owner_id = prompt_data['owner_id']
            shared_id = version_data['id']
            delete_public_version(shared_owner_id, shared_id, session)
            return session.commit()

    @web.event(PromptEvents.prompt_deleted)
    def prompt_deleted_handler(self, context, event, payload: dict):
        # payload = {
        #     'prompt_data': prompt_details.dict(),
        #     'public_id': public_id,
        #     'is_public': is_public
        # }
        prompt_data = payload['prompt_data']
        is_public = payload['is_public']
        public_id = payload.get('public_id')

        collections = group_by_project_id(prompt_data['collections'])
        for owner_id, collection_ids in collections.items():
            with db.get_session(owner_id) as session:
                delete_entity_from_collections(
                    entity_name='prompt',
                    collection_ids=collection_ids,
                    entity_data=prompt_data,
                    session=session
                )
                session.commit()

        if is_public:
            prompt_owner_id = prompt_data['shared_owner_id']
            prompt_id = prompt_data['shared_id']

            # close_private_versions
            with db.get_session(prompt_owner_id) as session:
                prompt = session.query(Prompt).get(prompt_id)

                if not prompt:
                    return

                session.query(PromptVersion).filter(
                    PromptVersion.prompt_id == prompt.id
                ).update({
                    PromptVersion.status: PublishStatus.draft
                })

                session.commit()
        elif public_id is not None:
            # delete_public_prompt
            prompt_owner_id = prompt_data['owner_id']
            prompt_id = prompt_data['id']
            with db.get_session(public_id) as session:
                prompt = session.query(Prompt).filter(
                    Prompt.shared_owner_id == prompt_owner_id,
                    Prompt.shared_id == prompt_id
                ).first()

                if not prompt:
                    return

                session.delete(prompt)
                session.commit()

    @web.event('prompt_public_version_status_change')
    def handle_on_moderation(self, context, event, payload: dict) -> None:
        # log.info(f'Event {payload}')
        private_project_id = payload['private_project_id']
        private_version_id = payload['private_version_id']
        status = payload['status']

        set_status(
            project_id=private_project_id,
            prompt_version_name_or_id=private_version_id,
            status=status
        )
