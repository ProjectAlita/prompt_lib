from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator
from .base import PromptTagBaseModel, PromptBaseModel, PromptVersionBaseModel, AuthorBaseModel, PromptVariableBaseModel, \
    PromptMessageBaseModel
from .list import PromptVersionListModel
from ..enums.all import PromptVersionStatus


class PromptMessageDetailModel(PromptMessageBaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVariableDetailModel(PromptVariableBaseModel):
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVersionDetailModel(PromptVersionBaseModel):
    id: int
    status: PromptVersionStatus
    created_at: datetime
    variables: Optional[List[PromptVariableDetailModel]]
    messages: Optional[List[PromptMessageDetailModel]]
    author: Optional[AuthorBaseModel]



class PromptDetailModel(PromptBaseModel):
    id: int
    versions: List[PromptVersionListModel]
    version_details: Optional[PromptVersionDetailModel]
    created_at: datetime

    # @validator('latest', pre=True, always=True)
    # def set_latest_version(cls, value, values, **kwargs):
    #     from pylon.core.tools import log
    #     # log.info('latest')
    #     log.info(value)
    #     # log.info(values)
    #     # log.info(kwargs)
    #     if value:
    #         return value
    #     for i in values['versions']:
    #         if i.name == 'latest':
    #             return i


