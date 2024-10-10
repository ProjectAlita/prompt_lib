from typing import List

from openai import BaseModel
from ...models.all import PromptVersion


class ForkPromptBase(BaseModel):
    target_project_id: int
    versions: List[PromptVersion]
