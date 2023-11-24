import json
from typing import List
from flask import request
from pydantic import ValidationError
from pylon.core.tools import log
from sqlalchemy import or_, and_

from tools import api_tools, auth, config as c

from ...models.all import Prompt
from ...models.pd.list import PromptListModel, PromptTagListModel
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    def get(self, project_id: int):
        args = request.args
        search_query = "%{}%".format(args.get('query', ''))
        filter_ = or_(Prompt.name.like(search_query),
                      Prompt.description.like(search_query))

        total, res = api_tools.get(
            project_id=project_id,
            args=args,
            data_model=Prompt,
            custom_filter=filter_,
            joinedload_=[Prompt.versions],
            is_project_schema=True
            )

        all_authors = set()
        parsed: List[PromptListModel] = []
        for prompt in res:
            prompt_data = PromptListModel.from_orm(prompt)
            tags = dict()
            for version in prompt.versions:
                for tag in version.tags:
                    tags[tag.name] = PromptTagListModel.from_orm(tag).dict()
                prompt_data.author_ids.add(version.author_id)
                all_authors.update(prompt_data.author_ids)
            prompt_data.tags = list(tags.values())
            parsed.append(prompt_data)

        users = auth.list_users(user_ids=list(all_authors))
        user_map = {i["id"]: i for i in users}

        for i in parsed:
            i.set_authors(user_map)

        return {
            "total": total,
            "rows": [json.loads(prompt.json(exclude={"author_ids"})) for prompt in parsed]
            }, 200

class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
