from typing import Optional

from ....promptlib_shared.models.pd.base import AuthorBaseModel


class AuthorDetailModel(AuthorBaseModel):
    id: Optional[int] = None
    title: Optional[str]
    description: Optional[str]
    public_prompts: int = 0
    total_prompts: int = 0
    public_collections: int = 0
    total_collections: int = 0
    rewards: int = 0
