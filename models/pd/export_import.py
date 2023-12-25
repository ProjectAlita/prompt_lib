from typing import Optional, List

from pydantic import AnyUrl, BaseModel
from pylon.core.tools import log
from .collections import CollectionModel


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


class DialPromptImportModel(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    content: str = ''
    model: Optional[DialModelImportModel]
    folderId: Optional[str]


class DialImportModel(BaseModel):
    prompts: List[DialPromptImportModel]
    folders: List[DialFolderImportModel]


class CollectionImportModel(CollectionModel):
    prompts: List[dict]

    class Config:
        orm_mode = True