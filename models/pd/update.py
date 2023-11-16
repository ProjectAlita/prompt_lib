from typing import List, Optional

from pydantic import validator
from .base import (
    PromptBaseModel,
    PromptVersionBaseModel,
    PromptVariableBaseModel,
    PromptMessageBaseModel,
    PromptTagBaseModel
)
from pylon.core.tools import log


class PromptUpdateModel(PromptBaseModel):
    id: int


class PromptVariableUpdateModel(PromptVariableBaseModel):
    id: Optional[int]


class PromptMessageUpdateModel(PromptMessageBaseModel):
    id: Optional[int]


class PromptTagUpdateModel(PromptTagBaseModel):
    id: Optional[int]


class PromptVersionUpdateModel(PromptVersionBaseModel):
    id: int
    variables: Optional[List[PromptVariableUpdateModel]] = []
    messages: Optional[List[PromptMessageUpdateModel]] = []
    tags: Optional[List[PromptTagUpdateModel]] = []

    @validator('name')
    def check_latest(cls, value: str):
        assert value == 'latest', "Only latest prompt version can be updated"
        return value
