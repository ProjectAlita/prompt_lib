from pydantic.v1 import BaseModel, constr


class VariableModel(BaseModel):
    prompt_id: int
    name: constr(regex=r'^[a-zA-Z_][a-zA-Z0-9_]*$', )
    value: str

    class Config:
        orm_mode = True


class VariableUpdateModel(VariableModel):
    id: int
