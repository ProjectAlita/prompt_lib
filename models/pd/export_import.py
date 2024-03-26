from typing import Optional, List

from pydantic import AnyUrl, BaseModel
from pylon.core.tools import log

from .model_settings import ModelSettingsBaseModel
from .prompt import PromptBaseModel
from .prompt_version import PromptVersionBaseModel
from ....promptlib_shared.models.pd.chat import IntegrationDataMixin
from .collections import CollectionModel, PromptIds


class PromptVersionExportModel(PromptVersionBaseModel):
    commit_message: Optional[str] = None
    context: Optional[str] = ''
    model_settings: ModelSettingsBaseModel


class PromptExportModel(PromptBaseModel):
    name: str
    description: Optional[str]
    owner_id: int
    versions: Optional[List[PromptVersionExportModel]]
    collection_id: Optional[int] = None

    class Config:
        fields = {
            'shared_id': {'exclude': True},
            'shared_owner_id': {'exclude': True},
        }
        orm_mode = True


class PromptImportModel(PromptExportModel):
    ...


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
                      prompt_ids: List[PromptIds] | None = None) -> CollectionModel:
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
