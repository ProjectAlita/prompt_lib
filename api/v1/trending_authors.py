from typing import List
from flask import jsonify
from pylon.core.tools import log

from tools import api_tools, auth, config as c

from ...utils.prompt_utils import get_trending_authors
from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.trending_authors.list"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    def get(self, project_id: int):
        authors: List[dict] = get_trending_authors(project_id)
        return jsonify(authors)

class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
