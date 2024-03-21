from datetime import datetime
from typing import List, Optional

from pylon.core.tools import log
from tools import auth

from pydantic import BaseModel, root_validator, validator
from ....promptlib_shared.models.enums.all import PublishStatus

from .base import PromptTagBaseModel, AuthorBaseModel
from ...utils.utils import determine_prompt_status, get_authors_data


class PromptTagListModel(PromptTagBaseModel):
    id: int


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


class PromptListModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime
    versions: List[PromptVersionListModel]
    author_ids: set[int] = set()
    authors: List[AuthorBaseModel] = []
    tags: Optional[PromptTagBaseModel]
    status: Optional[PublishStatus]

    class Config:
        orm_mode = True
        fields = {
            'author_ids': {'exclude': True},
            'versions': {'exclude': True},
        }

    @root_validator
    def parse_versions_data(cls, values):
        tags = dict()
        version_statuses = set()

        for version in values['versions']:
            for tag in version.tags:
                tags[tag.name] = tag
            values['author_ids'].add(version.author_id)
            version_statuses.add(version.status)

        values['tags'] = list(tags.values())
        values['status'] = determine_prompt_status(version_statuses)
        return values

    def set_authors(self, user_map: dict) -> None:
        self.authors = [
            AuthorBaseModel(**user_map[author_id]) for author_id in self.author_ids
        ]


class PublishedPromptListModel(PromptListModel):
    likes: Optional[int]
    is_liked: Optional[bool]
    trending_likes: Optional[int] = None

    class Config:
        from_orm = True

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
    

class MultiplePromptListModel(BaseModel):
    prompts: List[PromptListModel]

    @root_validator
    def parse_authors_data(cls, values):
        all_authors = set()
        for prompt in values['prompts']:
            all_authors.update(prompt.author_ids)

        users = get_authors_data(list(all_authors))
        user_map = {i['id']: i for i in users}

        for prompt in values['prompts']:
            prompt.set_authors(user_map)

        return values


class MultiplePublishedPromptListModel(MultiplePromptListModel):
    prompts: List[PublishedPromptListModel]


class MultiplePromptTagListModel(BaseModel):
    items: List[PromptTagListModel]


class PromptSearchModel(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MultiplePromptSearchModel(BaseModel):
    items: List[PromptSearchModel]