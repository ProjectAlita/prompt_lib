from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator
from .base import PromptTagBaseModel, AuthorBaseModel
from ..enums.all import PromptVersionStatus


class PromptTagListModel(PromptTagBaseModel):
    ...


class PromptVersionListModel(BaseModel):
    id: int
    prompt_id: int  # probably delete this
    name: str
    status: PromptVersionStatus
    created_at: datetime  # probably delete this


class PromptListModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime
    owner: Optional[AuthorBaseModel]
