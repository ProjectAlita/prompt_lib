from typing import Optional, List

from pydantic import BaseModel
from .base import PromptVersionBaseModel, PromptVariableBaseModel, PromptMessageBaseModel, ModelSettingsBaseModel
from ..enums.all import PromptVersionType
from pylon.core.tools import log


class PromptVersionPredictModel(BaseModel):
    context: Optional[str] = ''
    embedding_settings: Optional[dict]
    variables: Optional[List[PromptVariableBaseModel]] = []
    messages: Optional[List[PromptMessageBaseModel]] = []
    model_settings: Optional[ModelSettingsBaseModel] = {}
    embedding_settings: Optional[dict] = {}  # todo: create model for this field
    type: PromptVersionType = PromptVersionType.chat

    class Config:
        orm_mode = True

    def merge_update(self, other: 'PromptVersionPredictModel') -> 'PromptVersionPredictModel':
        this = self.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        updater = other.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        this.update(updater)
        return self.__class__.parse_obj(this)

