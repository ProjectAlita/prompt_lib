from datetime import datetime
from queue import Empty
from typing import Optional, List

from pydantic import BaseModel, validator, root_validator
from ....prompt_lib.models.pd.prompt_version import PromptVersionBaseModel, \
    PromptVersionLatestCreateModel, PromptVersionListModel, PromptVersionDetailModel, PublishedPromptVersionListModel
from ....prompt_lib.utils.utils import determine_prompt_status
from ....promptlib_shared.models.enums.all import PublishStatus
from ....promptlib_shared.models.pd.base import AuthorBaseModel, TagBaseModel

from tools import rpc_tools


class PromptBaseModel(BaseModel):
    name: str
    description: Optional[str]
    owner_id: int
    versions: Optional[List[PromptVersionBaseModel]]
    shared_id: Optional[int]
    shared_owner_id: Optional[int]

    class Config:
        orm_mode = True


class PromptCreateModel(PromptBaseModel):
    versions: List[PromptVersionLatestCreateModel]

    @validator('versions')
    def check_only_latest_version(cls, value: Optional[List[dict]], values: dict):
        assert len(value) == 1, 'Only 1 version can be created with prompt'
        return value


class PromptDetailModel(PromptBaseModel):
    id: int
    versions: List[PromptVersionListModel]
    version_details: Optional[PromptVersionDetailModel]
    created_at: datetime
    collections: Optional[list]
    owner_id: int


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


class PromptListModel(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime
    versions: List[PromptVersionListModel]
    author_ids: set[int] = set()
    authors: List[AuthorBaseModel] = []
    tags: Optional[TagBaseModel]
    status: Optional[PublishStatus]
    meta: Optional[dict] = dict()
    is_forked: bool = False

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

        for version in values.get('versions', []):
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

    @validator('description')
    def truncate_long_description(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return value[:64]
        return value

    @validator('is_forked', always=True)
    def set_is_forked(cls, v, values):
        meta = values['meta'] or {}
        if 'parent_entity_id' in meta and 'parent_project_id' in meta:
            return True
        return v


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


class PromptUpdateModel(PromptBaseModel):
    id: int
