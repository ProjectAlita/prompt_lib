from typing import List

from openai import BaseModel
from .export_import import PromptForkModel


class ForkPromptInput(BaseModel):
    prompts: List[PromptForkModel]

