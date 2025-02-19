from typing import List

from pydantic.v1 import BaseModel
from .export_import import PromptForkModel


class ForkPromptInput(BaseModel):
    prompts: List[PromptForkModel]

