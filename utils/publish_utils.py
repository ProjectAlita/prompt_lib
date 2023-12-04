import json
import hashlib
import uuid
import traceback

from tools import db, VaultClient
from pylon.core.tools import log

from ..models.all import Prompt, PromptVersion
from ..models.pd.create import PromptVersionBaseModel
from ..models.enums.all import PromptVersionStatus
from .create_utils import create_version


class Publishing:
    def __init__(self, project_id, prompt_version_id):
        self.public_version_id = None
        self.prompt_version_data = None
        self.prompt_data = None
        self.public_id = self._get_public_project_id()
        self.original_project = project_id
        self.original_version = prompt_version_id
        self._copy_version_id = None

    def _latest(self, prompt_version: PromptVersion) -> bool:
        return prompt_version.name == "latest"

    def _create_new_version(self, prompt_version: dict, prompt: Prompt, session=None, name:str=None) -> PromptVersion:
        prompt_data = PromptVersionBaseModel(**prompt_version)
        prompt_data.name = name or f'copy_{prompt_version["id"]}_' + str(uuid.uuid4())
        return create_version(prompt_data, prompt, session)

    def _create_prompt(self, prompt_data: dict, session=None) -> Prompt:
        data = {key:value for key, value in prompt_data.items() if key != 'id'}
        new_prompt = Prompt(**data)
        if session:
            session.add(new_prompt)
        return new_prompt

    def _get_public_project_id(self) -> int:
        secrets = VaultClient().get_all_secrets()
        public_id = secrets.get("ai_project_id")
        if public_id is None:
            raise Exception("Public project doesn't exists or ai_project_id is not set in secrets")
        return int(public_id)
    
    def set_private_prompt_data(self):
        with db.with_project_schema_session(self.original_project) as session:
            try:
                private_prompt_version = session.query(PromptVersion).get(self.original_version)
                if self._latest(private_prompt_version):
                    data = private_prompt_version.to_json()
                    prompt = private_prompt_version.prompt
                    private_prompt_version = self._create_new_version(data, prompt, session)
                    session.commit()
                    self._copy_version_id = private_prompt_version.id
                    self.original_version = self._copy_version_id

                # setting data
                self.prompt_version_data = private_prompt_version.to_json()
                self.prompt_data = private_prompt_version.prompt.to_json()
            except Exception as e:
                session.rollback()
                return {"ok": False, "error": str(e)}
            return {"ok": True}
    
    def undo_set_private_prompt_data(self):
        if not self._copy_version_id:
            return
        
        with db.with_project_schema_session(self.original_project) as session:
            try:
                session.query(PromptVersion).filter_by(id=self._copy_version_id).delete()
            except Exception as e:
                session.rollback()
                return {"ok": False, "error": str(e)}
            return {"ok": True}

    def get_origin_data(self):
        origin = {
            "owner_id": self.original_project,
            "id": self.original_version
        }
        json_string = json.dumps(origin, sort_keys=True)
        origin_hash = hashlib.md5(json_string.encode()).hexdigest()
        return origin, origin_hash

    def create_in_public(self):
        with db.with_project_schema_session(self.public_id) as session:
            try:
                origin, origin_hash = self.get_origin_data()                
                prompt = self._create_prompt(self.prompt_data)
                session.flush()

                self.prompt_version_data['prompt_id'] = prompt.id
                origin, origin_hash = self.get_origin_data()
                self.prompt_version_data['origin'] = origin
                self.prompt_version_data['origin_hash'] = origin_hash
                name = self.prompt_version_data['name']
                public_version = self._create_new_version(self.prompt_version_data, prompt, session, name)
                session.commit()
                self.public_version_id = public_version.id
            
            except Exception as e:
                session.rollback()
                return {"ok": False, "error": str(e)}
            return {"ok": True}

    def publish(self):
        published = self.check_already_published()
        if published:
            return {"ok": False, "error": 'already published'}

        result = self.set_private_prompt_data()
        if not result['ok']:
            return result
        
        result = self.create_in_public()
        if not result['ok']:
            self.undo_set_private_prompt_data()
        
        result = self.set_statuses(PromptVersionStatus.on_moderation)
        return result
    
    def check_already_published(self) -> bool:
        _, origin_hash = self.get_origin_data()
        with db.with_project_schema_session(self.public_id) as session:
            return session.query(PromptVersion).filter_by(origin_hash=origin_hash).first()
    
    def _set_status(self, project_id, id, status: PromptVersionStatus):
        with db.with_project_schema_session(project_id) as session:
            try:
                version = session.query(PromptVersion).filter_by(id=id).first()
                version.status = status
                session.commit()
            except Exception as e:
                log.info(traceback.format_exc())
                session.rollback()
                return {
                    "ok": False, 
                    "error": f"Error happened while setting status for project_id={project_id}, id={id}, status={status}"
                }
        return {"ok": True}
    
    def set_statuses(self, status: PromptVersionStatus):
        if not (self.public_version_id and self.original_project):
            return
        # set status of private prompt version
        result = self._set_status(self.original_project, self._copy_version_id, status)
        # set status of public prompt version
        result = self._set_status(self.public_id, self.public_version_id, status)
        return result