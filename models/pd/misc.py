from typing import List

from pydantic import BaseModel, root_validator
from ....prompt_lib.models.pd.prompt import PromptListModel, PublishedPromptListModel
from ....prompt_lib.models.pd.search import PromptSearchModel
from ....prompt_lib.models.pd.tag import PromptTagListModel
from ....prompt_lib.utils.utils import get_authors_data


class MultiplePromptListModel(BaseModel):
    prompts: List[PromptListModel]

    @root_validator
    def parse_authors_data(cls, values):
        all_authors = set()
        for prompt in values['prompts']:
            all_authors.update(prompt.author_ids)

        users = get_authors_data(list(all_authors))
        user_map = {i['id']: i for i in users}

        for prompt in values['prompts']:
            prompt.set_authors(user_map)

        return values


class MultiplePublishedPromptListModel(MultiplePromptListModel):
    prompts: List[PublishedPromptListModel]


class MultiplePromptTagListModel(BaseModel):
    items: List[PromptTagListModel]


class MultiplePromptSearchModel(BaseModel):
    items: List[PromptSearchModel]
