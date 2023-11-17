from typing import Optional, List, Literal

from pydantic import validator
from .base import PromptBaseModel, PromptVersionBaseModel
from ..enums.all import PromptVersionType
from pylon.core.tools import log


class PromptVersionCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat

    @validator('name')
    def check_latest(cls, value: str) -> str:
        assert value != 'latest', "Name of created prompt version can not be 'latest'"
        return value


class PromptVersionLatestCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat
    name: Literal['latest'] = 'latest'


class PromptCreateModel(PromptBaseModel):
    versions: List[PromptVersionLatestCreateModel]

    @validator('versions')
    def check_only_latest_version(cls, value: Optional[List[dict]], values: dict):
        assert len(value) == 1, 'Only 1 version can be created with prompt'
        return value
