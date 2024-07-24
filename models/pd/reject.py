from typing import Optional

from pydantic import BaseModel


class RejectPromptInput(BaseModel):
    reject_details: Optional[str] = None
