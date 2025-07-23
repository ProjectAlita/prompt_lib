from datetime import datetime
from typing import Optional

from pydantic.v1 import BaseModel
from ....prompt_lib.models.enums.all import MessageRoles


class PromptMessageBaseModel(BaseModel):
    role: MessageRoles
    name: Optional[str]
    content: Optional[str]
    custom_content: Optional[dict]

    class Config:
        orm_mode = True
