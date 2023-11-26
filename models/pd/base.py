from typing import Optional, List

from pydantic import (
    BaseModel,
    PositiveInt,
    ConstrainedFloat,
    StrictStr,
    constr,
    confloat,
    conint,
)
from ..enums.all import MessageRoles, PromptVersionType


class ModelInfoBaseModel(BaseModel):
    name: str
    integration_uid: StrictStr
    integration_name: Optional[str]


class ModelSettingsBaseModel(BaseModel):
    temperature: Optional[confloat(ge=0, le=2)] = None
    top_k: Optional[conint(ge=1, le=40)] = None
    top_p: Optional[confloat(ge=0, le=1)] = None
    max_tokens: Optional[PositiveInt] = None
    stream: bool = False
    model: Optional[ModelInfoBaseModel] = {}
    suggested_models: Optional[list] = []


class PromptTagBaseModel(BaseModel):
    name: str
    data: Optional[dict]

    class Config:
        orm_mode = True


class PromptMessageBaseModel(BaseModel):
    role: MessageRoles
    name: Optional[str]
    content: Optional[str]
    custom_content: Optional[dict]

    class Config:
        orm_mode = True


class PromptVariableBaseModel(BaseModel):
    name: constr(
        regex=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    value: Optional[str] = ""
    prompt_version_id: Optional[int]

    class Config:
        orm_mode = True


class PromptVersionBaseModel(BaseModel):
    name: str
    commit_message: Optional[str]
    author_id: int
    context: Optional[str]
    variables: Optional[List[PromptVariableBaseModel]]
    messages: Optional[List[PromptMessageBaseModel]]
    tags: Optional[List[PromptTagBaseModel]]
    model_settings: Optional[ModelSettingsBaseModel]
    embedding_settings: Optional[dict]  # todo: create model for this field
    type: PromptVersionType
    prompt_id: Optional[int]

    class Config:
        orm_mode = True


class PromptBaseModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    versions: Optional[List[PromptVersionBaseModel]]

    class Config:
        orm_mode = True


class AuthorBaseModel(BaseModel):
    id: int
    email: str
