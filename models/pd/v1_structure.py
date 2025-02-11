import enum
from typing import List, Optional

from pydantic.v1 import BaseModel, validator, root_validator
from pylon.core.tools import log

from ...utils.ai_providers import AIProvider
from tools import rpc_tools

class TagV1Model(BaseModel):
    id: int
    tag: str
    color: Optional[str]

    class Config:
        fields = {
            'tag': 'name'
        }

    @root_validator(pre=True)
    def parse_values(cls, values):
        values['color'] = values.get('data', {}).get('color')
        return values


class VersionV1Model(BaseModel):
    id: int
    version: Optional[str]
    tags: List[TagV1Model] = []

    @root_validator(pre=True)
    def parse_values(cls, values):
        values['version'] = values['name']
        return values


class PromptV1Model(BaseModel):
    id: int
    integration_uid: Optional[str] = None
    name: str
    description: str | None
    prompt: Optional[str]
    test_input: Optional[str] = None
    is_active_input: bool = False
    type: str
    model_settings: dict | None = None
    created_at: Optional[str]
    updated_at: Optional[str]
    version: Optional[str] = 'latest'
    embeddings: Optional[dict] = {}
    tags: List[TagV1Model] = []
    versions: List[VersionV1Model] = []

    @root_validator(pre=True)
    def parse_values(cls, values):
        if values.get('versions'):
            latest_version = next(version for version in values['versions'] if version['name'] == 'latest')
            if latest_version:
                values['type'] = latest_version['type']
                values['created_at'] = latest_version['created_at']
                values['prompt'] = latest_version['context']
                values['tags'] = latest_version['tags']
                if latest_version.get('model_settings'):
                    model = latest_version['model_settings'].pop('model', {})
                    values['integration_uid'] = model.get('integration_uid')
                    values['model_settings'] = latest_version['model_settings']
        return values


class PromptType(str, enum.Enum):
    chat = 'chat'
    structured = 'structured'
    freeform = 'freeform'


class PromptCreateV1Model(BaseModel):
    name: str
    description: str | None
    prompt: str
    project_id: Optional[int] = None
    test_input: Optional[str] = None
    integration_uid: Optional[str] = None
    type: PromptType = PromptType.structured
    model_settings: dict | None = None
    version: Optional[str] = 'latest'
    is_active_input: bool = True

    class Config:
        use_enum_values = True

    @root_validator
    def check_settings(cls, values: dict):
        if not (values['project_id'] and values['integration_uid']):
            return values
        project_id, integration_uid = values['project_id'], values['integration_uid']
        integration = AIProvider.get_integration(project_id, integration_uid)
        model_settings = values['model_settings']
        response = AIProvider.parse_settings(integration, model_settings)
        if not response['ok']:
            raise response['error']
        values['model_settings'] = response['item']
        return values


class PromptUpdateV1Model(PromptCreateV1Model):
    id: int
    version: Optional[str]
    embedding: Optional[int]
    embedding_settings: Optional[dict]


    @validator('embedding_settings', pre=True, always=True)
    def set_embedding_settings(cls, value: Optional[dict], values: dict):
        if not int(values['embedding']):
            return {}
        embedding = rpc_tools.RpcMixin().rpc.timeout(2).embeddings_get_by_id(
            values['project_id'], values['embedding']
            )
        if not embedding:
            return {}
        if not value:
            value = {}
        value = {
            **embedding.to_json(),
            'top_k': value.get('top_k', 20),
            'cutoff': value.get('cutoff', 0.1),
        }
        return value


class PromptUpdateNameV1Model(BaseModel):
    name: str
