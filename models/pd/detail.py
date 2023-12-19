from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator
from .base import PromptTagBaseModel, PromptBaseModel, PromptVersionBaseModel, AuthorBaseModel, PromptVariableBaseModel, \
    PromptMessageBaseModel
from .list import PromptVersionListModel
from ..enums.all import PromptVersionStatus
from ...utils.utils import get_author_data


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

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        author_data = get_author_data(values['author_id'])
        return AuthorBaseModel(**author_data)


class PromptDetailModel(PromptBaseModel):
    id: int
    versions: List[PromptVersionListModel]
    version_details: Optional[PromptVersionDetailModel]
    created_at: datetime


class PublishedPromptVersionListModel(PromptVersionListModel):
    author: Optional[AuthorBaseModel]

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        author_data = get_author_data(values['author_id'])
        return AuthorBaseModel(**author_data)


class PublishedPromptDetailModel(PromptDetailModel):
    versions: List[PublishedPromptVersionListModel]

    @validator('versions')
    def check_versions(cls, value: list) -> list:
        return [version for version in value if version.status == PromptVersionStatus.published]
