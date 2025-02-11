from typing import Optional

from pydantic.v1 import BaseModel


class RejectPromptInput(BaseModel):
    reject_details: Optional[str] = None
