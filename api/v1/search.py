import json
from typing import List
from flask import request
from pylon.core.tools import log
from sqlalchemy import or_

from tools import api_tools, auth, config as c

from ...models.all import Prompt
from ...models.pd.list import MultiplePromptListModel
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.prompts.search"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
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

        parsed = MultiplePromptListModel(prompts=res)

        return {
            "total": total,
            "rows": [json.loads(prompt.json()) for prompt in parsed.prompts]
            }, 200

class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
