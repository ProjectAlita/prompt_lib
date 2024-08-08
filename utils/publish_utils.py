import json

from sqlalchemy.orm import aliased
from sqlalchemy.sql import exists, and_
from tools import db, VaultClient, auth, rpc_tools
from pylon.core.tools import log

from ..models.all import Prompt, PromptVersion
from .create_utils import create_version
from ..models.pd.prompt_version import PromptVersionDetailModel, PromptVersionBaseModel
from ...promptlib_shared.models.enums.all import PublishStatus, NotificationEventTypes


def set_status(project_id: int, prompt_version_name_or_id: int | str, status: PublishStatus, return_data=False) -> dict:
    f = [PromptVersion.name == prompt_version_name_or_id]
    if isinstance(prompt_version_name_or_id, int):
        f = [PromptVersion.id == prompt_version_name_or_id]
    log.info(f'set_status {project_id=} {prompt_version_name_or_id=} {status=}')
    with db.with_project_schema_session(project_id) as session:
        try:
            version = session.query(PromptVersion).filter(*f).first()
            if not version:
                return {
                    "ok": False,
                    "error": f"Version with id/name '{prompt_version_name_or_id}' not found",
                    "error_code": 404,
                }
            version.status = status
            session.commit()
            if return_data:
                version_detail = PromptVersionDetailModel.from_orm(version)
        except Exception as e:
            log.error(e)
            session.rollback()
            return {
                "ok": False,
                "error": f"Error happened while setting status for {project_id=}, {prompt_version_name_or_id=}, {status=}"
            }

    if return_data:
        return {"ok": True, "result": json.loads(version_detail.json())}
    return {"ok": True}


class Publishing(rpc_tools.EventManagerMixin):
    def __init__(self, project_id: int, prompt_version_id: int):
        self.public_version_id = None
        self.prompt_version_data = None
        self.prompt_data = None
        self.public_id = self._get_public_project_id()
        self.original_project = project_id
        self.original_version = prompt_version_id

    def _latest(self, prompt_version: PromptVersion) -> bool:
        return prompt_version.name == "latest"

    def _create_new_version(self, prompt_version: dict, prompt: Prompt, session=None) -> PromptVersion:
        prompt_data = PromptVersionBaseModel(**prompt_version)
        return create_version(prompt_data, prompt, session)

    def _create_prompt(self, prompt_data: dict, session=None) -> Prompt:
        new_prompt = Prompt(**prompt_data)
        if session:
            session.add(new_prompt)
        return new_prompt

    def _get_public_project_id(self) -> int:
        secrets = VaultClient().get_all_secrets()
        try:
            return int(secrets['ai_project_id'])
        except (KeyError, ValueError):
            raise Exception("Public project doesn't exist")

    def __jsonify_relationships(self, items):
        result = []
        for item in items:
            instance = item.to_json()
            instance.pop('id', None)
            instance.pop('prompt_version_id', None)
            instance.pop('created_at', None)
            instance.pop('updated_at', None)
            result.append(instance)
        return result

    def _publishing_from_public(self):
        # update PromptVersion status to on_moderation
        with db.with_project_schema_session(self.original_project) as session:
            version = session.query(PromptVersion).get(self.original_version)
            if not version:
                return {"ok": False, "error": f"Prompt version with id '{self.original_version}' not found"}
            version.status = PublishStatus.on_moderation
            session.commit()
        return {"ok": True}

    def prepare_private_prompt_data(self):
        with db.with_project_schema_session(self.original_project) as session:
            try:
                private_prompt_version = session.query(PromptVersion).get(self.original_version)
                if not private_prompt_version:
                    return {
                        "ok": False,
                        "error": f"Prompt version with id '{self.original_version}' not found",
                        "error_code": 404
                    }

                if self._latest(private_prompt_version):
                    return {"ok": False, "error": "Version 'latest' cannot be published"}

                # setting data
                self.prompt_version_data: dict = private_prompt_version.to_json()
                self.prompt_version_data.pop('created_at', None)
                self.prompt_version_data.pop('id', None)
                self.prompt_version_data.pop('prompt_id', None)
                self.prompt_version_data['shared_owner_id'] = self.original_project
                self.prompt_version_data['shared_id'] = self.original_version
                #
                self.prompt_version_data['messages'] = self.__jsonify_relationships(private_prompt_version.messages)
                self.prompt_version_data['tags'] = self.__jsonify_relationships(private_prompt_version.tags)
                self.prompt_version_data['variables'] = self.__jsonify_relationships(private_prompt_version.variables)

                # setting prompt shared data
                self.prompt_data = private_prompt_version.prompt.to_json()
                self.prompt_data.pop('created_at', None)
                self.prompt_data['shared_owner_id'] = self.prompt_data.pop('owner_id')
                self.prompt_data['shared_id'] = self.prompt_data.pop('id')
                self.prompt_data['owner_id'] = self.public_id
            except Exception as e:
                session.rollback()
                return {"ok": False, "error": str(e)}
            return {"ok": True}

    def create_in_public(self):
        with db.with_project_schema_session(self.public_id) as session:
            try:
                prompt = self.get_public_prompt()
                new_prompt_created = False
                prompt_collections = None
                if not prompt:
                    new_prompt_created = True
                    prompt_collections = self.prompt_data['collections']
                    self.prompt_data['collections'] = []
                    prompt = self._create_prompt(self.prompt_data)
                    session.flush()

                self.prompt_version_data['prompt_id'] = prompt.id
                public_version = self._create_new_version(self.prompt_version_data, prompt, session)
                session.commit()
                self.public_version_id = public_version.id
                if new_prompt_created:
                    fire_public_prompt_created(prompt.to_json(), prompt_collections)
            except Exception as e:
                session.rollback()
                return {"ok": False, "error": str(e)}
            return {"ok": True}

    def publish(self):
        if self.public_id == self.original_project:
            result = self._publishing_from_public()
            if not result['ok']:
                return result
            return self.retrieve_private_prompt()

        result = self.prepare_private_prompt_data()
        if not result['ok']:
            return result

        published = self.check_already_published()
        if published:
            return {"ok": False, "error": 'Already published'}

        result = self.create_in_public()
        if not result['ok']:
            return result

        result = self.set_statuses(PublishStatus.on_moderation)
        if not result['ok']:
            return result

        return self.retrieve_private_prompt()

    def get_public_prompt(self) -> bool:
        shared_id = self.prompt_data['shared_id']
        shared_owner_id = self.prompt_data['shared_owner_id']
        with db.with_project_schema_session(self.public_id) as session:
            prompt = session.query(Prompt).filter_by(
                shared_id=shared_id, shared_owner_id=shared_owner_id
            ).first()
            return prompt

    def check_already_published(self) -> bool:
        shared_id = self.prompt_data['shared_id']
        shared_owner_id = self.prompt_data['shared_owner_id']
        name = self.prompt_version_data['name']
        with db.with_project_schema_session(self.public_id) as session:
            prompt_alias = aliased(Prompt)
            exists_query = (
                session.query(exists().where(and_(
                    prompt_alias.shared_id == shared_id,
                    prompt_alias.shared_owner_id == shared_owner_id,
                    PromptVersion.prompt_id == prompt_alias.id,
                    PromptVersion.name == name,
                )))
            ).scalar()

            return exists_query

    def set_statuses(self, status: PublishStatus):
        if not (self.public_version_id and self.original_project):
            return

        # set status of public prompt version
        result = set_status(project_id=self.public_id, prompt_version_name_or_id=self.public_version_id, status=status)
        # if result['ok']:
        #     self.event_manager.fire_event('prompt_public_version_status_change', {
        #         'public_project_id': self.public_id,
        #         'public_version_id': self.public_version_id,
        #         'status': status
        #     })

        # set status of private prompt version
        result = set_status(self.original_project, self.original_version, status)
        return result

    def retrieve_private_prompt(self):
        with db.with_project_schema_session(self.original_project) as session:
            version = session.query(PromptVersion).filter_by(id=self.original_version).first()
            version_details = PromptVersionDetailModel.from_orm(version)
            return {"ok": True, "prompt_version": json.loads(version_details.json())}


def close_private_version(shared_owner_id, shared_id, session):
    version = session.query(PromptVersion).filter_by(id=shared_id).first()
    if not version:
        log.warning(f"Private prompt version is not found(shared_id={shared_id}, shared_owner_id={shared_owner_id})")
        return

    version.status = PublishStatus.draft


def delete_public_version(shared_owner_id, shared_id, session):
    version = session.query(PromptVersion).filter_by(
        shared_id=shared_id,
        shared_owner_id=shared_owner_id
    ).first()
    if version:
        session.delete(version)


def delete_public_prompt_versions(prompt_owner_id, prompt_id, session):
    prompt = session.query(Prompt).filter_by(
        shared_owner_id=prompt_owner_id,
        shared_id=prompt_id
    ).first()
    #
    if not prompt:
        return
    #
    versions = session.query(PromptVersion).filter(PromptVersion.prompt_id == prompt.id)
    for version in versions:
        session.delete(version)


def fire_public_prompt_created(prompt_data, collections):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        "prompt_lib_entity_published",
        {
            "entity_data": prompt_data,
            "collections": collections,
            "entity_name": "prompt"
        }
    )


def fire_version_deleted_event(project_id, version: dict, prompt: dict):
    # todo: refactor!
    try:
        public, public_id = is_public_project(project_id)
    except Exception:
        log.error("No public project is not set and post prompt deletion event is skipped")
        return
    payload = {
        'prompt_data': prompt,
        'version_data': version,
        'project_id': project_id,
        'public_id': public_id,
    }
    prefix = "private" if not public else "public"

    rpc_tools.EventManagerMixin().event_manager.fire_event(
        f'{prefix}_prompt_version_deleted', payload
    )


def is_public_project(project_id: int = None):
    ai_project_id = get_public_project_id()
    return ai_project_id == project_id, int(ai_project_id)


def get_public_project_id():
    secrets = VaultClient().get_all_secrets()
    project_id = secrets.get("ai_project_id")
    if not project_id:
        raise Exception("Public project is not set")
    return int(project_id)


def unpublish(current_user_id, project_id, version_id):
    public_id = get_public_project_id()
    with db.with_project_schema_session(public_id) as session:
        version = session.query(PromptVersion).filter_by(
            shared_id=version_id,
            shared_owner_id=project_id
        ).first()
        if not version:
            return {
                "ok": False,
                "error": f"Public version with id '{version_id}'",
                "error_code": 404,
            }

        if int(version.author_id) != int(current_user_id):
            return {
                "ok": False,
                "error": "Current user is not author of the prompt version",
                "error_code": 403
            }

        if version.status in [PublishStatus.draft, PublishStatus.rejected]:
            return {"ok": False, "error": "Version is not public yet"}

        version_data = version.to_json()
        prompt_data = version.prompt.to_json()
        session.delete(version)
        session.commit()
        fire_version_deleted_event(public_id, version_data, prompt_data)
        return {"ok": True, "msg": "Successfully unpublished"}


def set_public_version_status(
        version_id: int, status: PublishStatus, *,
        reject_details: str = None):
    public_id = get_public_project_id()
    result = set_status(
        project_id=public_id,
        prompt_version_name_or_id=version_id,
        status=status,
        return_data=True
    )
    log.info(f'Result: {result["result"]}')
    if result['ok']:
        prompt_version_data = result['result']

        event_manager = rpc_tools.EventManagerMixin().event_manager

        event_manager.fire_event(
            'prompt_public_version_status_change', {
                'private_project_id': prompt_version_data['shared_owner_id'],
                'private_version_id': prompt_version_data['shared_id'],
                'status': status
            })

        prompt_project_id = prompt_version_data['shared_owner_id'] or public_id
        prompt_version_id = prompt_version_data['shared_id'] or version_id
        notification_type = None
        match status:
            case PublishStatus.published:
                notification_type = NotificationEventTypes.prompt_moderation_approve
            case PublishStatus.rejected:
                notification_type = NotificationEventTypes.prompt_moderation_reject

        if notification_type:
            with db.get_session(prompt_project_id) as session:
                original_prompt = session.query(
                    Prompt.id,
                    Prompt.name,
                    PromptVersion.name
                ).join(
                    Prompt.versions
                ).where(
                    PromptVersion.id == prompt_version_id
                ).first()

                if original_prompt:
                    prompt_id, prompt_name, prompt_version_name = original_prompt
                    event_manager.fire_event(
                        'notifications_stream', {
                            'project_id': prompt_project_id,
                            'user_id': prompt_version_data['author']['id'],
                            'meta': {
                                'prompt_version_id': prompt_version_id,
                                'prompt_version_name': prompt_version_name,
                                'prompt_id': prompt_id,
                                'prompt_name': prompt_name,
                                'reject_details': reject_details,
                                'public_prompt_id': prompt_version_data.get('prompt_id'),
                                'public_prompt_version_id': prompt_version_data.get('id'),
                            },
                            'event_type': notification_type
                        }
                    )
                    if PublishStatus.rejected:
                        session.query(PromptVersion).filter(
                            PromptVersion.id == version_id
                        ).update(
                            {PromptVersion.meta: {'reject_details': reject_details}}
                        )
                        session.commit()

    return result
