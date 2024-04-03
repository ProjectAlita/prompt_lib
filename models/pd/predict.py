import uuid
from typing import Optional, List, Any

from pydantic import BaseModel, validator, Field
from .model_settings import ModelSettingsBaseModel
from .prompt_message import PromptMessageBaseModel
from .prompt_variable import PromptVariableBaseModel
from ..enums.all import PromptVersionType
from pylon.core.tools import log
import re

from ...utils.ai_providers import AIProvider, IntegrationNotFound


class PromptMessagePredictModel(PromptMessageBaseModel):
    @validator('name')
    def sanitize_name(cls, value: str):
        if value:
            sanitized = re.findall(r'[a-zA-Z0-9_-]+', value)
            return ''.join(sanitized)
        return value


class PromptVersionPredictModel(BaseModel):
    project_id: int
    prompt_version_id: Optional[int] = None
    message_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    user_name: Optional[str] = None

    context: Optional[str] = ''
    variables: Optional[List[PromptVariableBaseModel]] = []
    messages: Optional[List[PromptMessagePredictModel]] = []
    model_settings: Optional[ModelSettingsBaseModel] = ModelSettingsBaseModel()
    embedding_settings: Optional[dict] = {}  # todo: create model for this field
    type: PromptVersionType = PromptVersionType.chat
    user_input: Optional[str]
    chat_history: Optional[List[PromptMessagePredictModel]] = []
    integration: Optional[Any] = None

    class Config:
        orm_mode = True

    def merge_update(self, other: 'PromptVersionPredictModel') -> 'PromptVersionPredictModel':
        this = self.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        updater = other.dict(exclude_unset=True, exclude_none=True, )
        this.update(updater)
        return self.__class__.parse_obj(this)

    @validator('integration', always=True)
    def set_integration(cls, value, values):
        if value is None:
            log.info(f'{value=} {values=}')
            integration_uid = values['model_settings'].model.integration_uid
            try:
                return AIProvider.get_integration(
                    project_id=values['project_id'],
                    integration_uid=integration_uid,
                )
            except IntegrationNotFound:
                raise ValueError(f'Integration not found with uid {integration_uid}')

    @property
    def merged_settings(self) -> dict:
        return {**self.integration.settings, **self.model_settings.merged}
