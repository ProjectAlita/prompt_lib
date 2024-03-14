import uuid
from typing import Optional, List

from pydantic import BaseModel, validator, Field
from .base import PromptVariableBaseModel, PromptMessageBaseModel, ModelSettingsBaseModel
from ..enums.all import PromptVersionType
from pylon.core.tools import log
import re


class PromptMessagePredictModel(PromptMessageBaseModel):
    @validator('name')
    def sanitize_name(cls, value: str):
        if value:
            sanitized = re.findall(r'[a-zA-Z0-9_-]+', value)
            return ''.join(sanitized)
        return value


class PromptVersionPredictModel(BaseModel):
    context: Optional[str] = ''
    variables: Optional[List[PromptVariableBaseModel]] = []
    messages: Optional[List[PromptMessagePredictModel]] = []
    model_settings: Optional[ModelSettingsBaseModel] = {}
    embedding_settings: Optional[dict] = {}  # todo: create model for this field
    type: PromptVersionType = PromptVersionType.chat
    user_input: Optional[str]
    chat_history: Optional[List[PromptMessagePredictModel]] = []

    class Config:
        orm_mode = True

    def merge_update(self, other: 'PromptVersionPredictModel') -> 'PromptVersionPredictModel':
        this = self.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        updater = other.dict(exclude_unset=True, exclude_none=True, )
        this.update(updater)
        return self.__class__.parse_obj(this)


class PromptVersionPredictStreamModel(PromptVersionPredictModel):
    project_id: int
    prompt_version_id: Optional[int] = None
    message_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    user_name: Optional[str] = None
