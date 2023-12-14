import json

from tools import db, VaultClient, auth

from ..models.all import Prompt, PromptVersion
from ..models.pd.create import PromptVersionBaseModel
from ..models.enums.all import PromptVersionStatus
from .create_utils import create_version
from ..models.pd.detail import PromptVersionDetailModel


class Publishing:
    def __init__(self, project_id, prompt_version_id):
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
        public_id = secrets.get("ai_project_id")
        if public_id is None:
            raise Exception("Public project doesn't exists or ai_project_id is not set in secrets")
        return int(public_id)

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
                if not prompt:
                    prompt = self._create_prompt(self.prompt_data)
                    session.flush()

                self.prompt_version_data['prompt_id'] = prompt.id
                public_version = self._create_new_version(self.prompt_version_data, prompt, session)
                session.commit()
                self.public_version_id = public_version.id
            except Exception as e:
                session.rollback()
                return {"ok": False, "error": str(e)}
            return {"ok": True}

    def publish(self):
        result = self.prepare_private_prompt_data()
        if not result['ok']:
            return result

        published = self.check_already_published()
        if published:
            return {"ok": False, "error": 'Already published'}

        result = self.create_in_public()
        if not result['ok']:
            return result

        result = self.set_statuses(PromptVersionStatus.on_moderation)
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
        prompt_id = self.prompt_data['shared_id']
        name = self.prompt_version_data['name']
        with db.with_project_schema_session(self.public_id) as session:
            prompt_version = session.query(PromptVersion).filter_by(name=name, prompt_id=prompt_id).first()
            return bool(prompt_version)

    def _set_status(self, project_id, id, status: PromptVersionStatus):
        with db.with_project_schema_session(project_id) as session:
            try:
                version = session.query(PromptVersion).filter_by(id=id).first()
                version.status = status
                session.commit()
            except Exception as e:
                session.rollback()
                return {
                    "ok": False,
                    "error": f"Error happened while setting status for project_id={project_id}, id={id}, status={status}"
                }
        return {"ok": True}

    def set_statuses(self, status: PromptVersionStatus):
        if not (self.public_version_id and self.original_project):
            return

        # set status of public prompt version
        result = self._set_status(self.public_id, self.public_version_id, status)
        if not result['ok']:
            return result

        # set status of private prompt version
        result = self._set_status(self.original_project, self.original_version, status)
        return result

    def retrieve_private_prompt(self):
        with db.with_project_schema_session(self.original_project) as session:
            version = session.query(PromptVersion).filter_by(id=self.original_version).first()
            version_details = PromptVersionDetailModel.from_orm(version)
            return {"ok": True, "prompt_version": json.loads(version_details.json())}
