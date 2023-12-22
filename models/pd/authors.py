from datetime import datetime
from typing import Optional, List
from .base import AuthorBaseModel


class AuthorDetailModel(AuthorBaseModel):
    title: Optional[str]
    description: Optional[str]
    public_prompts: int = 0


class TrendingAuthorModel(AuthorBaseModel):
    last_login: Optional[datetime]
    likes: int = 0
