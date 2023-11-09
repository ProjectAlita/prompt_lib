from typing import Optional, List

from pydantic import validator
from .base import PromptBaseModel, PromptVersionBaseModel
from ..enums.all import PromptVersionType


class PromptVersionCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat

    @validator('name')
    def check_latest(cls, value: str):
        assert value == 'latest', "Name of created prompt version can only be 'latest'"
        return value


class PromptCreateModel(PromptBaseModel):
    versions: List[PromptVersionCreateModel]

    @validator('versions', pre=True)
    def set_author_from_owner(cls, value: Optional[List[dict]], values: dict):
        assert len(value) == 1, 'Only 1 version can be created with prompt'
        if value and 'author_id' not in value:
            for version in value:
                version['author_id'] = values.get('owner_id')
        return value
