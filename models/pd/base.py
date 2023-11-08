from typing import Optional, List

from pydantic import BaseModel, validator
from .create import PromptTagCreateModel
from ..enums.all import MessageRoles, PromptVersionType


class ModelSettingsBaseModel(BaseModel):
    top_k: float
#     todo: finish this


class PromptTagBaseModel(BaseModel):
    name: str
    data: Optional[dict]


class PromptMessageBaseModel(BaseModel):
    role: MessageRoles
    name: Optional[str]
    content: Optional[str]
    custom_content: Optional[dict]


class PromptVariableBaseModel(BaseModel):
    name: str
    value: Optional[str]


class PromptVersionBaseModel(BaseModel):
    name: str
    commit_message: Optional[str]
    author_id: int
    context: Optional[str]
    embedding_settings: Optional[dict]
    variables: Optional[List[PromptVariableBaseModel]]
    messages: Optional[List[PromptMessageBaseModel]]
    tags: Optional[List[PromptTagBaseModel]]
    model_settings: Optional[ModelSettingsBaseModel]
    embedding_settings: Optional[dict]  # todo: create model for this field
    type: PromptVersionType


class PromptBaseModel(BaseModel):
    name: str
    description: Optional[str]
    owner_id: int
    versions: Optional[List[PromptVersionBaseModel]]


class AuthorBaseModel(BaseModel):
    id: int
    email: str
