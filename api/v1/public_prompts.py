import json
from flask import request

from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth

from ...models.pd.list import MultiplePublishedPromptListModel
from ...models.enums.all import PromptVersionStatus

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils import list_prompts_api
from ...utils.utils import add_public_project_id


class PromptLibAPI(api_tools.APIModeHandler):
    @add_public_project_id
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.public_prompts.list"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def get(self, *, project_id: int, **kwargs):
        some_result = list_prompts_api(
            project_id=project_id,
            tags=request.args.get('tags'),
            author_id=request.args.get('author_id'),
            q=request.args.get('query'),
            limit=request.args.get("limit", default=10, type=int),
            offset=request.args.get("offset", default=0, type=int),
            sort_by=request.args.get("sort_by", default="created_at"),
            sort_order=request.args.get("sort_order", default='desc'),
            my_liked=request.args.get('my_liked', False),
            trend_start_period=request.args.get('trend_start_period'),
            trend_end_period=request.args.get('trend_end_period'),
            statuses=[PromptVersionStatus.published]
        )
        parsed = MultiplePublishedPromptListModel(prompts=some_result['prompts'])
        return {
            'total': some_result['total'],
            'rows': [
                json.loads(i.json(exclude={'status'}, exclude_unset=True))
                for i in parsed.prompts
            ]
        }, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "",
        ]
    )

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
