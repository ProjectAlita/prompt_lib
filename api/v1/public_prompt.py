import json

from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from ...utils.prompt_utils import get_published_prompt_details, add_publuc_project_id
from ...utils.constants import PROMPT_LIB_MODE

from tools import api_tools, auth, config as c


class PromptLibAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.prompt.details"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    @add_publuc_project_id
    def get(self, prompt_id: int, version_name: str = None, **kwargs):
        ai_project_id = kwargs.get('project_id')
        result = get_published_prompt_details(ai_project_id, prompt_id, version_name)

        if not result['ok']:
            return {'error': result['msg']}, 400
        return json.loads(result['data']), 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:prompt_id>',
        '<int:prompt_id>/<string:version_name>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
