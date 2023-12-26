from datetime import datetime
from typing import Optional, List

# from pylon.core.tools import log
from pydantic import BaseModel, root_validator
from .base import AuthorBaseModel
from .list import PromptListModel
from .detail import PromptTagDetailModel
from ..enums.all import CollectionPatchOperations


class PromptIds(BaseModel):
    id: int
    owner_id: int


class CollectionPatchModel(BaseModel):
    operation: CollectionPatchOperations
    prompt: PromptIds


class CollectionModel(BaseModel):
    name: str
    owner_id: int
    author_id: Optional[int]
    description: Optional[str]
    prompts: Optional[List[PromptIds]] = []
    shared_id: Optional[int]
    shared_owner_id: Optional[int]


class PromptBaseModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int

    class Config:
        orm_mode = True


class CollectionDetailModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    status: str
    author_id: int
    prompts: Optional[List[PromptListModel]] = []
    author: Optional[AuthorBaseModel]
    created_at: datetime

    class Config:
        orm_mode = True


class CollectionUpdateModel(BaseModel):
    name: Optional[str]
    description: Optional[str]
    owner_id: Optional[int]
    status: str
    prompts: Optional[List[PromptIds]] = {}


class CollectionListModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    author_id: int
    status: str
    author: Optional[AuthorBaseModel]
    prompts: Optional[List] = []
    tags: List[PromptTagDetailModel] = []
    created_at: datetime
    likes: int = 0

    class Config:
        orm_mode = True
        fields = {
            "prompts": {"exclude": True},
        }

    @root_validator
    def count_prompts(cls, values):
        count = len(values.get("prompts"))
        values["prompt_count"] = count
        return values

