from typing import Optional, List

from pydantic import validator
from .base import PromptBaseModel, PromptVersionBaseModel
from ..enums.all import PromptVersionType


class PromptVersionCreateModel(PromptVersionBaseModel):
    type: PromptVersionType = PromptVersionType.chat


class PromptCreateModel(PromptBaseModel):
    versions: Optional[List[PromptVersionCreateModel]]

    @validator('versions', pre=True)
    def set_author_from_owner(cls, value: Optional[List[dict]], values: dict):
        if value and 'author_id' not in value:
            for version in value:
                version['author_id'] = values.get('owner_id')
        return value
