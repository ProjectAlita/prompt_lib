from pydantic import BaseModel


class ExampleModel(BaseModel):
    prompt_id: int
    input: str
    output: str
    is_active: bool = True

    class Config:
        orm_mode = True


class ExampleUpdateModel(ExampleModel):
    id: int
