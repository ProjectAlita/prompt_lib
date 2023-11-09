from pydantic import BaseModel, validator, constr


class PromptTagModel(BaseModel):
    tag: constr(to_lower=True)
    color: str
    
    class Config:
        orm_mode = True
