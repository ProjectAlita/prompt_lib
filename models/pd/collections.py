from datetime import datetime
from queue import Empty
from typing import Optional, List
from pydantic import BaseModel, Field, root_validator, validator

from pylon.core.tools import log
from tools import rpc_tools

from .prompt import PromptListModel
from ....promptlib_shared.models.pd.base import AuthorBaseModel
from ....promptlib_shared.models.pd.entity import EntityListModel
from ....promptlib_shared.models.pd.tag import TagDetailModel
from ....promptlib_shared.utils.constants import ENTITY_DESCRIPTION_LEN_LIMITATION_4_LIST_API
from ..enums.all import CollectionPatchOperations
from ...utils.publish_utils import get_public_project_id


class CollectionItem(BaseModel):
    id: int
    owner_id: int

    class Config:
        orm_mode = True


class CollectionPrivateTwinModel(BaseModel):
    id: int = Field(..., alias='shared_id')
    owner_id: int = Field(..., alias='shared_owner_id')

    class Config:
        orm_mode = True


class CollectionPatchModel(BaseModel):
    project_id: int
    collection_id: int
    operation: CollectionPatchOperations
    prompt: Optional[CollectionItem] = None
    datasource: Optional[CollectionItem] = None
    application: Optional[CollectionItem] = None

    @root_validator(pre=True)
    def check_only_one_entity(cls, values):
        fields = ("prompt", "datasource", "application",)
        if [bool(values.get(f)) for f in fields].count(True) != 1:
            raise ValueError(f'One non-empty of the fields is expected: {fields}')

        return values


class CollectionModel(BaseModel):
    name: str
    owner_id: int
    author_id: Optional[int]
    description: Optional[str]
    prompts: Optional[List[CollectionItem]] = []
    datasources: Optional[List[CollectionItem]] = []
    applications: Optional[List[CollectionItem]] = []
    shared_id: Optional[int]
    shared_owner_id: Optional[int]


# class PromptBaseModel(BaseModel):
#     id: int
#     name: str
#     description: Optional[str]
#     owner_id: int
#
#     class Config:
#         orm_mode = True


class CollectionShortDetailModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    status: str

    class Config:
        orm_mode = True


class CollectionDetailModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    status: str
    author_id: int
    prompts: Optional[List[EntityListModel]] = []
    datasources: Optional[List[EntityListModel]] = []
    applications: Optional[List[EntityListModel]] = []
    author: Optional[AuthorBaseModel]
    created_at: datetime

    class Config:
        orm_mode = True


class CollectionUpdateModel(BaseModel):
    name: Optional[str]
    description: Optional[str]
    status: str


class CollectionListModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    author_id: int
    status: str
    author: Optional[AuthorBaseModel]
    prompts: Optional[List] = []
    datasources: Optional[List] = []
    applications: Optional[List] = []
    tags: List[TagDetailModel] = []
    created_at: datetime
    includes_prompt: Optional[bool] = None
    includes_datasource: Optional[bool] = None
    includes_application: Optional[bool] = None
    prompt_addability: Optional[bool] = None
    datasource_addability: Optional[bool] = None
    application_addability: Optional[bool] = None
    prompt_count: int = 0
    datasource_count: int = 0
    application_count: int = 0
    likes: Optional[int]
    trending_likes: Optional[int]
    is_liked: Optional[bool]

    class Config:
        orm_mode = True
        fields = {
            "prompts": {"exclude": True},
            "datasources": {"exclude": True},
            "applications": {"exclude": True},
        }

    @root_validator
    def count_entities(cls, values):
        values["prompt_count"] = len(values.get("prompts"))
        values["datasource_count"] = len(values.get("datasources"))
        values["application_count"] = len(values.get("applications"))
        return values

    @validator('is_liked')
    def is_liked_field(cls, v):
        if v is None:
            return False
        return v

    @validator('likes')
    def likes_field(cls, v):
        if v is None:
            return 0
        return v

    @validator('description')
    def truncate_long_description(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return value[:ENTITY_DESCRIPTION_LEN_LIMITATION_4_LIST_API]
        return value


class PublishedCollectionDetailModel(CollectionDetailModel):
    likes: Optional[int] = 0
    is_liked: Optional[bool] = False

    def get_likes(self, project_id: int) -> None:
        try:
            likes_data = rpc_tools.RpcMixin().rpc.timeout(2).social_get_likes(
                project_id=project_id, entity='collection', entity_id=self.id
            )
            # self.likes = [LikeModel(**like) for like in likes_data['rows']]
            self.likes = likes_data['total']
        except Empty:
            self.likes = 0

    def check_is_liked(self, project_id: int) -> None:
        try:
            self.is_liked = rpc_tools.RpcMixin().rpc.timeout(2).social_is_liked(
                project_id=project_id, entity='collection', entity_id=self.id
            )
        except Empty:
            self.is_liked = False


class CollectionSearchModel(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MultipleCollectionSearchModel(BaseModel):
    items: List[CollectionSearchModel]
