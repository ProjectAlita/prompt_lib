from typing import Optional, List

from pydantic import validator
from .base import PromptBaseModel, PromptVersionBaseModel
from ..enums.all import PromptVersionType
from pylon.core.tools import log

class PromptVersionCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat

    @validator('name')
    def check_latest(cls, value: str):
        assert value == 'latest', "Name of created prompt version can only be 'latest'"
        return value


class PromptCreateModel(PromptBaseModel):
    versions: List[PromptVersionCreateModel]

    @validator('versions')
    def check_only_latest_version(cls, value: Optional[List[dict]], values: dict):
        assert len(value) == 1, 'Only 1 version can be created with prompt'
        return value
