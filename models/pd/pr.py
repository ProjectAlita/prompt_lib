from typing import List

from openai import BaseModel


class PullRequestCompare(BaseModel):
    added: List[dict] = []
    removed: List[dict] = []
    modified: dict = {}


class PullRequestResponse(BaseModel):
    prompt_diff: PullRequestCompare
    versions_diff: List[PullRequestCompare]


class CreatePullRequestBase(BaseModel):
    source_project_id: int
