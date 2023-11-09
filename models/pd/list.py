from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator
from .base import PromptTagBaseModel, AuthorBaseModel, PromptVersionBaseModel
from ..enums.all import PromptVersionStatus


class PromptTagListModel(PromptTagBaseModel):
    id: int


class PromptVersionListModel(BaseModel):
    id: int
    name: str
    status: PromptVersionStatus
    created_at: datetime  # probably delete this

    class Config:
        orm_mode = True


class PromptListModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime
    owner: Optional[AuthorBaseModel]
    tags: Optional[PromptTagBaseModel]

    class Config:
        orm_mode = True

    # @validator('tags', 'versions', pre=True, always=True)
    # def get_tags(cls, value, values):
    #     from pylon.core.tools import log
    #     log.info('valllllllllllll')
    #     log.info(value)
    #     log.info(values)
    #     log.info('valllllllllllll')
    #     return value
