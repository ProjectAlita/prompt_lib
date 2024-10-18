from typing import Optional, List

from pydantic import AnyUrl, BaseModel

from .model_settings import ModelSettingsBaseModel
from .prompt_message import PromptMessageBaseModel
from .prompt_variable import PromptVariableBaseModel
from ..enums.all import PromptVersionType
from ....promptlib_shared.models.pd.base import TagBaseModel
from ....promptlib_shared.models.pd.chat import IntegrationDataMixin
from .collections import CollectionModel, CollectionItem


class PromptVersionExportModel(BaseModel):
    name: str
    commit_message: Optional[str] = None
    context: Optional[str] = ''
    variables: Optional[List[PromptVariableBaseModel]]
    messages: Optional[List[PromptMessageBaseModel]]
    tags: Optional[List[TagBaseModel]]
    model_settings: Optional[ModelSettingsBaseModel]
    type: Optional[PromptVersionType] = PromptVersionType.chat
    author_id: int
    meta: Optional[dict]

    class Config:
        orm_mode = True


class PromptExportModel(BaseModel):
    name: str
    description: Optional[str]
    versions: Optional[List[PromptVersionExportModel]]
    collection_id: Optional[int] = None

    class Config:
        orm_mode = True


class PromptVersionForkModel(PromptVersionExportModel):
    id: int
    name: Optional[str]
    author_id: Optional[str]


class PromptForkModel(PromptExportModel):
    id: int
    owner_id: int
    name: Optional[str]
    versions: List[PromptVersionForkModel]


class PromptImportModel(PromptExportModel):
    owner_id: Optional[int]


class DialModelExportModel(BaseModel):
    id: str
    name: Optional[str]
    iconUrl: Optional[AnyUrl]
    type: Optional[str]
    maxLength: Optional[int]
    requestLimit: Optional[int]
    isDefault: Optional[bool]


class DialModelImportModel(DialModelExportModel):
    ...


class DialFolderImportModel(BaseModel):
    id: str
    name: str
    type: str

    def to_collection(self, project_id: int,
                      author_id: int,
                      prompt_ids: List[CollectionItem] | None = None) -> CollectionModel:
        if not prompt_ids:
            prompt_ids = []
        return CollectionModel(
            name=self.name,
            owner_id=project_id,
            author_id=author_id,
            prompts=prompt_ids
        )


class DialFolderExportModel(DialFolderImportModel):
    ...


class DialPromptExportModel(BaseModel):
    id: str
    name: str
    description: str
    content: str
    model: Optional[DialModelExportModel]
    folderId: Optional[str]


class DialPromptImportModel(DialPromptExportModel):
    id: Optional[str]
    description: Optional[str]
    content: str = ''
    model: Optional[DialModelImportModel]
    folderId: Optional[str]
    alita_model: IntegrationDataMixin


class DialExportModel(BaseModel):
    prompts: List[DialPromptExportModel]
    folders: List[DialFolderExportModel]


class DialImportModel(DialExportModel):
    prompts: List[DialPromptImportModel]
    folders: List[DialFolderImportModel]
