from typing import Optional, List, Dict
from pydantic import BaseModel, root_validator
from .base import (
    AuthorBaseModel,
    PromptBaseModel,
    PromptMessageBaseModel,
    PromptVariableBaseModel,
    PromptTagBaseModel,
    ModelSettingsBaseModel,
    PromptVersionType,
)


class PromptIds(BaseModel):
    id: int
    project_id: int


class CollectionModel(BaseModel):
    name: str
    owner_id: int
    author_id: Optional[int]
    prompts: Optional[List[PromptIds]] = []


class PromptVersionModel(BaseModel):
    version_name: str
    commit_message: Optional[str]
    author_id: int
    context: Optional[str]
    variables: Optional[List[PromptVariableBaseModel]]
    messages: Optional[List[PromptMessageBaseModel]]
    tags: Optional[List[PromptTagBaseModel]]
    model_settings: Optional[ModelSettingsBaseModel]
    embedding_settings: Optional[dict]  # todo: create model for this field
    type: PromptVersionType
    prompt_name: Optional[str]
    description: Optional[str]
    owner_id: Optional[int]
    prompt: PromptBaseModel

    class Config:
        orm_mode = True
        fields = {
            "version_name": "name",
            "prompt": {"exclude": True},
            "author_id": {"exclude": True},
        }

    @root_validator
    def extract_prompt_name(cls, values):
        prompt = values.get("prompt")
        if prompt:
            values["prompt_name"] = prompt.name
            values["description"] = prompt.description
            values["owner_id"] = prompt.owner_id
        return values


class MultiplePromptVersionModel(BaseModel):
    prompts: Optional[List[PromptVersionModel]]


class CollectionDetailModel(BaseModel):
    id: int
    name: str
    owner_id: int
    author_id: int
    prompts: Optional[List[PromptVersionModel]]
    # prompts: Optional[Dict[int, int]] = {}
    author: Optional[AuthorBaseModel]

    class Config:
        orm_mode = True


class CollectionUpdateModel(BaseModel):
    name: Optional[str]
    owner_id: Optional[int]
    prompts: Optional[List[PromptIds]] = {}


class CollectionListModel(BaseModel):
    id: int
    name: str
    owner_id: int
    author_id: int
    author: Optional[AuthorBaseModel]

    class Config:
        orm_mode = True
