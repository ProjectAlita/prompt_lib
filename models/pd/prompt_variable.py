from datetime import datetime
from typing import Optional

from pydantic import BaseModel, constr


class PromptVariableBaseModel(BaseModel):
    name: constr(
        regex=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    value: Optional[str] = ""
    prompt_version_id: Optional[int]

    class Config:
        orm_mode = True


class PromptVariableDetailModel(PromptVariableBaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class PromptVariableUpdateModel(PromptVariableBaseModel):
    id: Optional[int]
