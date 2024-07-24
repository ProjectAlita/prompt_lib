from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, validator
from .model_settings import ModelSettingsCreateModel, ModelSettingsBaseModel
from .prompt_message import PromptMessageBaseModel, PromptMessageDetailModel, PromptMessageUpdateModel
from .prompt_variable import PromptVariableBaseModel, PromptVariableDetailModel, PromptVariableUpdateModel
from .tag import PromptTagListModel, PromptTagUpdateModel
from ..enums.all import PromptVersionType
from ...utils.utils import get_authors_data
from ....promptlib_shared.models.enums.all import PublishStatus
from ....promptlib_shared.models.pd.base import TagBaseModel, AuthorBaseModel
from ....promptlib_shared.models.pd.tag import TagDetailModel


class PromptVersionBaseModel(BaseModel):
    name: str
    commit_message: Optional[str]
    author_id: int
    context: Optional[str]
    variables: Optional[List[PromptVariableBaseModel]]
    messages: Optional[List[PromptMessageBaseModel]]
    tags: Optional[List[TagBaseModel]]
    model_settings: Optional[ModelSettingsBaseModel]
    embedding_settings: Optional[dict]  # todo: create model for this field
    type: PromptVersionType
    prompt_id: Optional[int]
    shared_id: Optional[int]
    shared_owner_id: Optional[int]
    conversation_starters: Optional[List]
    welcome_message: Optional[str]

    class Config:
        orm_mode = True


class PromptVersionListModel(BaseModel):
    id: int
    name: str
    status: PublishStatus
    created_at: datetime  # probably delete this
    author_id: int
    tags: List[PromptTagListModel]
    author: Optional[AuthorBaseModel]

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        authors_data: list = get_authors_data(author_ids=[values['author_id']])
        if authors_data:
            return AuthorBaseModel(**authors_data[0])

    class Config:
        orm_mode = True
        fields = {
            'tags': {'exclude': True},
        }


class PromptVersionCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat
    model_settings = ModelSettingsCreateModel

    @validator('name')
    def check_latest(cls, value: str) -> str:
        assert value != 'latest', "Name of created prompt version can not be 'latest'"
        return value


class PromptVersionLatestCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat
    name: Literal['latest'] = 'latest'
    model_settings = ModelSettingsCreateModel


class PromptVersionUpdateModel(PromptVersionBaseModel):
    id: Optional[int]
    type: Optional[PromptVersionType]
    name: Literal['latest']
    variables: Optional[List[PromptVariableUpdateModel]] = []
    messages: Optional[List[PromptMessageUpdateModel]] = []
    tags: Optional[List[PromptTagUpdateModel]] = []

    # @validator('name')
    # def check_latest(cls, value: str):
    #     assert value == 'latest', "Only latest prompt version can be updated"
    #     return value


class PromptVersionDetailModel(PromptVersionBaseModel):
    id: int
    status: PublishStatus
    created_at: datetime
    variables: Optional[List[PromptVariableDetailModel]]
    messages: Optional[List[PromptMessageDetailModel]]
    author: Optional[AuthorBaseModel]
    tags: Optional[List[TagDetailModel]]

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        authors_data: list = get_authors_data(author_ids=[values['author_id']])
        if authors_data:
            return AuthorBaseModel(**authors_data[0])


class PublishedPromptVersionListModel(PromptVersionListModel):
    author: Optional[AuthorBaseModel]

    @validator('author', always=True)
    def add_author_data(cls, value: dict, values: dict) -> AuthorBaseModel:
        authors_data: list = get_authors_data(author_ids=[values['author_id']])
        if authors_data:
            return AuthorBaseModel(**authors_data[0])
