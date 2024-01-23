import json
from flask import request
from pylon.core.tools import log
from tools import api_tools, auth, config as c
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.searches import list_search_requests
from ...models.pd.search import SearchRequestsListModel


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.search_requests.list"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id: int):
        args = request.args
        total, searches = list_search_requests(project_id, args)
        parsed = SearchRequestsListModel(searches=searches)
        return {
            'total': total,
            'rows': [
                json.loads(i.json())
                for i in parsed.searches
            ]
        }, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:project_id>",
        ]
    )


    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
