import enum
from typing import List, Optional

from pydantic import BaseModel, validator, root_validator, ValidationError
from pylon.core.tools import log


class TagV1Model(BaseModel):
    id: int
    name: str
    color: Optional[str]


class VersionV1Model(BaseModel):
    id: int
    version: Optional[str]
    tags: List[TagV1Model] = []

    @root_validator(pre=True)
    def parse_values(cls, values):
        values['version'] = values['name']
        if values.get('tags'):
            values['tags'] = [tag | tag.get('data', {}) for tag in values['tags']]
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
                values['tags'] = [tag | tag.get('data', {}) for tag in latest_version['tags']]
                if latest_version.get('model_settings'):
                    model = latest_version['model_settings'].pop('model', {})
                    values['integration_uid'] = model.get('integration_uid')
                    values['model_settings'] = latest_version['model_settings']
        return values
