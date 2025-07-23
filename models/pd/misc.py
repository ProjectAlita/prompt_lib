from typing import List

from pydantic.v1 import BaseModel
from ....prompt_lib.models.pd.tag import PromptTagListModel


class MultiplePromptTagListModel(BaseModel):
    items: List[PromptTagListModel]

