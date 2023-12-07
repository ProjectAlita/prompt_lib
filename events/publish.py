from pylon.core.tools import log, web

from tools import db, VaultClient

from sqlalchemy.orm import joinedload
from ..models.all import PromptVersion
from ..models.enums.all import PromptVersionStatus

from ..utils.publish_utils import set_status

from time import sleep
from ..utils.publish_utils import (
    close_private_version,
    close_private_prompt,
    delete_public_prompt,
    delete_public_version
)


class Event:
    @web.event("prompt_deleted")
    def handler(self, context, event, payload: dict):
        secrets = VaultClient().get_all_secrets()
        public_id = secrets.get("ai_project_id")

        if not public_id:
            log.warning("No public project is not set and post prompt deletion event is skipped")
            return

        project_id = payload.get('project_id')
        version_data = payload.get('version_data')
        prompt_data = payload.get('prompt_data')

        if not int(project_id) == int(public_id):
            # deletion in private project, then
            with db.with_project_schema_session(public_id) as session:
                prompt_owner_id = prompt_data['owner_id']
                prompt_id = prompt_data['id']
                if version_data:
                    # version is deleted, then
                    version_name = version_data['name']
                    delete_public_version(prompt_owner_id, prompt_id, version_name, session)
                    return session.commit()

                # private prompt is deleted, then
                delete_public_prompt(prompt_owner_id, prompt_id, session)
                return session.commit()

        # deletion in public
        shared_id = prompt_data['shared_id']
        shared_owner_id = prompt_data['shared_owner_id']

        with db.with_project_schema_session(shared_owner_id) as session:
            if version_data:
                # version is deleted
                version_name = version_data['name']
                close_private_version(shared_owner_id, shared_id, version_name, session)
                return session.commit()

            # prompt is deleted
            close_private_prompt(shared_owner_id, shared_id, session)
            return session.commit()

    @web.event('prompt_public_version_status_change')
    def handle_on_moderation(self, context, event, payload: dict) -> None:
        log.info(f'EVEnt {payload}')

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
