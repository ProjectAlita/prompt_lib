from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from .base import PromptTagBaseModel, PromptBaseModel, PromptVersionBaseModel, AuthorBaseModel, PromptVariableBaseModel, \
    PromptMessageBaseModel
from .list import PromptVersionListModel
from ..enums.all import PromptVersionStatus


class PromptMessageDetailModel(PromptMessageBaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVariableDetailModel(PromptVariableBaseModel):
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVersionDetailModel(PromptVersionBaseModel):
    id: int
    status: PromptVersionStatus
    created_at: datetime
    variables: Optional[List[PromptVariableDetailModel]]
    messages: Optional[List[PromptMessageDetailModel]]


class PromptDetailModel(PromptBaseModel):
    id: int
    versions: List[PromptVersionListModel]
    latest: PromptVersionDetailModel
    created_at: datetime
    owner: Optional[AuthorBaseModel]
