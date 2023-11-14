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
    author_ids: set[int] = set()
    authors: list[AuthorBaseModel] = []
    tags: Optional[PromptTagBaseModel]

    class Config:
        orm_mode = True

    def set_authors(self, user_map: dict) -> None:
        self.authors = [
            user_map.get(i) for i in self.author_ids
        ]



