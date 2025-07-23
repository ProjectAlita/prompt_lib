from typing import List
from pydantic.v1 import BaseModel


class SearchRequestModel(BaseModel):
    search_keyword: str
    count: int

    class Config:
        orm_mode = True


class SearchRequestsListModel(BaseModel):
    searches: List[SearchRequestModel]
