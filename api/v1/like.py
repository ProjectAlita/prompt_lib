from flask import request
from sqlalchemy.exc import IntegrityError

from pylon.core.tools import log
from tools import api_tools, auth, config as c

from ...utils.constants import PROMPT_LIB_MODE


class PromptLibAPI(api_tools.APIModeHandler):

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.like.create"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def post(self, project_id, entity, entity_id):
        try:
            result = self.module.context.rpc_manager.call.social_like(
                project_id=project_id, entity=entity, entity_id=entity_id)
        except IntegrityError:
            return {"ok": False, "error": "Already liked"}, 400
        return result, 201

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompt_lib.like.delete"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def delete(self, project_id, entity, entity_id):
        result = self.module.context.rpc_manager.call.social_dislike(
            project_id=project_id, entity=entity, entity_id=entity_id)
        return result, 204


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:project_id>/<string:entity>/<int:entity_id>",
        ]
    )

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
