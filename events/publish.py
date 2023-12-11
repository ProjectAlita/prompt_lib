from pylon.core.tools import log, web

from tools import db

from sqlalchemy.orm import joinedload
from ..models.all import PromptVersion
from ..models.enums.all import PromptVersionStatus

from ..utils.publish_utils import set_status

from time import sleep
from ..utils.publish_utils import (
    close_private_version, 
    delete_public_prompt_versions,
    delete_public_version,
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
            delete_public_prompt_versions(prompt_owner_id, prompt_id, session)
            return session.commit()


    @web.event('prompt_public_version_status_change')
    def handle_on_moderation(self, context, event, payload: dict) -> None:
        log.info(f'Event {payload}')

        public_project_id = payload['public_project_id']
        public_version_id = payload['public_version_id']
        status = payload['status']
        with db.with_project_schema_session(public_project_id) as session:
            public_version: PromptVersion = session.query(PromptVersion).options(
                joinedload(PromptVersion.prompt)
            ).filter(
                PromptVersion.id == public_version_id,
            ).first()
            set_status(
                project_id=public_version.prompt.shared_owner_id,
                # prompt_version_id=public_version.prompt.shared_id,
                prompt_version_name_or_id=public_version.name,
                status=status
            )

            if status == PromptVersionStatus.on_moderation:
                new_status = PromptVersionStatus.published
                for i in public_version.tags:
                    if i.name == PromptVersionStatus.rejected:
                        new_status = PromptVersionStatus.rejected
                        break
                payload['status'] = new_status
                sleep(60)
                public_version.status = new_status
                session.commit()
                context.event_manager.fire_event('prompt_public_version_status_change', payload)

 
