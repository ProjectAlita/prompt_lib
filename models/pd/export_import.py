from typing import Optional, List

from pydantic import AnyUrl, BaseModel
from pylon.core.tools import log

from .model_settings import ModelSettingsBaseModel, ModelSettingsCreateModel
from .prompt_message import PromptMessageBaseModel
from .prompt_variable import PromptVariableBaseModel
from .prompt_version import PromptVersionBaseModel
from ..enums.all import PromptVersionType
from ....promptlib_shared.models.pd.base import TagBaseModel
from ....promptlib_shared.models.pd.chat import IntegrationDataMixin
from .collections import CollectionModel, PromptIds, PromptBaseModel


class PromptVersionExportModel(BaseModel):
    name: str
    commit_message: Optional[str] = None
    author_id: int
    context: Optional[str] = ''
    variables: Optional[List[PromptVariableBaseModel]]
    messages: Optional[List[PromptMessageBaseModel]]
    tags: Optional[List[TagBaseModel]]
    model_settings: ModelSettingsCreateModel
    type: PromptVersionType = PromptVersionType.chat
    prompt_id: Optional[int]


class PromptExportModel(BaseModel):
    name: str
    description: Optional[str]
    owner_id: int
    versions: Optional[List[PromptVersionExportModel]]

    class Config:
        fields = {
            'shared_id': {'exclude': True},
            'shared_owner_id': {'exclude': True},
        }


class DialModelImportModel(BaseModel):
    id: str
    name: Optional[str]
    iconUrl: Optional[AnyUrl]
    type: Optional[str]
    maxLength: Optional[int]
    requestLimit: Optional[int]
    isDefault: Optional[bool]


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


class DialPromptImportModel(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    content: str = ''
    model: Optional[DialModelImportModel]
    folderId: Optional[str]
    alita_model: IntegrationDataMixin


class DialExportModel(BaseModel):
    prompts: List[DialPromptImportModel]
    folders: List[DialFolderImportModel]


class DialImportModel(DialExportModel):
    # chat_settings_ai: IntegrationDataMixin
    ...

class CollectionImportModel(CollectionModel):
    prompts: List[dict]

    class Config:
        orm_mode = True
