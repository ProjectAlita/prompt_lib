from flask import request
from pydantic import ValidationError

from pylon.core.tools import log
from tools import api_tools, auth, config as c

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.collections import get_collection
from ...utils.utils import add_public_project_id



class PromptLibAPI(api_tools.APIModeHandler):
    @add_public_project_id
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.public_collection.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, collection_id: int, *, project_id, **kwargs):
        result = get_collection(project_id, collection_id, only_public=True)
        if not result:
            return {"error": f"No collection found with id '{collection_id}'"}, 404
        return result, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:collection_id>",
        ]
    )

    mode_handlers = {PROMPT_LIB_MODE: PromptLibAPI}
