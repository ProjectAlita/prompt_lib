from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator
from .base import PromptTagBaseModel, PromptBaseModel, PromptVersionBaseModel, AuthorBaseModel, PromptVariableBaseModel, \
    PromptMessageBaseModel
from .list import PromptVersionListModel
from ..enums.all import PromptVersionStatus


class PromptTagDetailModel(PromptTagBaseModel):
    id: int


class PromptMessageDetailModel(PromptMessageBaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVariableDetailModel(PromptVariableBaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVersionDetailModel(PromptVersionBaseModel):
    id: int
    status: PromptVersionStatus
    created_at: datetime
    variables: Optional[List[PromptVariableDetailModel]]
    messages: Optional[List[PromptMessageDetailModel]]
    author: Optional[AuthorBaseModel]
    tags: Optional[List[PromptTagDetailModel]]


class PromptDetailModel(PromptBaseModel):
    id: int
    versions: List[PromptVersionListModel]
    version_details: Optional[PromptVersionDetailModel]
    created_at: datetime

class PublishedPromptDetailModel(PromptDetailModel):
    version_statuses: Optional[List[PromptVersionStatus]]
