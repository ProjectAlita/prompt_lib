from datetime import datetime
from queue import Empty
from typing import List, Optional
from pydantic import BaseModel, validator

from tools import rpc_tools

from ....promptlib_shared.models.enums.all import PublishStatus
from .base import (
    PromptTagBaseModel,
    PromptBaseModel,
    PromptVersionBaseModel,
    AuthorBaseModel,
    PromptVariableBaseModel,
    PromptMessageBaseModel
)
from .list import PromptVersionListModel
from ...utils.utils import get_authors_data


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
    status: PublishStatus
    created_at: datetime
    variables: Optional[List[PromptVariableDetailModel]]
    messages: Optional[List[PromptMessageDetailModel]]
    author: Optional[AuthorBaseModel]
    tags: Optional[List[PromptTagDetailModel]]

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        authors_data: list = get_authors_data(author_ids=[values['author_id']])
        if authors_data:
            return AuthorBaseModel(**authors_data[0])


class PromptDetailModel(PromptBaseModel):
    id: int
    versions: List[PromptVersionListModel]
    version_details: Optional[PromptVersionDetailModel]
    created_at: datetime
    collections: Optional[list]


class PublishedPromptVersionListModel(PromptVersionListModel):
    author: Optional[AuthorBaseModel]

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        authors_data: list = get_authors_data(author_ids=[values['author_id']])
        if authors_data:
            return AuthorBaseModel(**authors_data[0])


# class LikeModel(BaseModel):
#     user_id: int
#     created_at: datetime
#     author: Optional[AuthorBaseModel]

#     class Config:
#         fields = {
#             "user_id": {"exclude": True}
#         }

#     @validator('author', always=True)
#     def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
#         author_data = get_author_data(values['user_id'])
#         if author_data:
#             return AuthorBaseModel(**author_data)

class PublishedPromptDetailModel(PromptDetailModel):
    versions: List[PublishedPromptVersionListModel]
    # likes: List[LikeModel] = []
    likes: int = 0
    is_liked: bool = False

    @validator('versions')
    def check_versions(cls, value: list) -> list:
        return [version for version in value if version.status == PublishStatus.published]

    def get_likes(self, project_id: int) -> None:
        try:
            likes_data = rpc_tools.RpcMixin().rpc.timeout(2).social_get_likes(
                project_id=project_id, entity='prompt', entity_id=self.id
            )
            # self.likes = [LikeModel(**like) for like in likes_data['rows']]
            self.likes = likes_data['total']
        except Empty:
            self.likes = 0

    def check_is_liked(self, project_id: int) -> None:
        try:
            self.is_liked = rpc_tools.RpcMixin().rpc.timeout(2).social_is_liked(
                project_id=project_id, entity='prompt', entity_id=self.id
            )
        except Empty:
            self.is_liked = False
