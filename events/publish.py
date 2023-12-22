from pylon.core.tools import log, web

from tools import db

from sqlalchemy.orm import joinedload
from ..models.all import PromptVersion
from ..models.enums.all import PromptVersionStatus

from ..utils.publish_utils import set_status

from ..utils.publish_utils import (
    close_private_version, 
    fire_prompt_deleted_event,
    delete_public_prompt,
    delete_public_version,
    close_private_versions
)


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

    @web.event("private_prompt_deleted")
    def handler(self, context, event, payload: dict):
        prompt_data = payload['prompt_data']
        public_id = payload['public_id']
        #
        with db.with_project_schema_session(public_id) as session:
            prompt_owner_id = prompt_data['owner_id']
            prompt_id = prompt_data['id']
            delete_public_prompt(prompt_owner_id, prompt_id, session)
            session.commit()
            return fire_prompt_deleted_event(public_id, prompt_data)


    @web.event("public_prompt_deleted")
    def handler(self, context, event, payload: dict):
        prompt_data = payload['prompt_data']
        #
        prompt_owner_id = prompt_data['shared_owner_id']
        prompt_id = prompt_data['shared_id']
        close_private_versions(prompt_owner_id, prompt_id)
            

    @web.event('prompt_public_version_status_change')
    def handle_on_moderation(self, context, event, payload: dict) -> None:
        log.info(f'Event {payload}')
        private_project_id = payload['private_project_id']
        private_version_id = payload['private_version_id']
        status = payload['status']

        set_status(
            project_id=private_project_id,
            prompt_version_name_or_id=private_version_id,
            status=status
        )
