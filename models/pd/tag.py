from typing import Optional

from ....promptlib_shared.models.pd.base import TagBaseModel


class PromptTagListModel(TagBaseModel):
    id: int


class PromptTagDetailModel(TagBaseModel):
    id: int


class PromptTagUpdateModel(TagBaseModel):
    id: Optional[int]
