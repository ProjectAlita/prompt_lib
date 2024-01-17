import traceback
from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from ...utils.constants import PROMPT_LIB_MODE

from tools import api_tools, config as c, auth


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.feedback.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, feedback_id: int):
        result = self.module.context.rpc_manager.call.social_get_feedback(feedback_id)
        if not result['ok']:
            return result, 404
        result['result'] = result['result'].to_json()
        return result, 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.feedback.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def delete(self, project_id, feedback_id):
        result = self.module.context.rpc_manager.call.social_delete_feedback(feedback_id)
        return "", 204 if result['ok'] else 404

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.feedback.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def put(self, project_id, feedback_id):
        try:
            payload = request.get_json()
            rpc = self.module.context.rpc_manager.call
            FeedbackUpdateModel = rpc.social_get_feedback_validator(operation="update")
            FeedbackUpdateModel.validate(payload)
            result = rpc.social_update_feedback(feedback_id, payload)
            if not result['ok']:
                return result, 404
            result['result'] = result['result'].to_json()
            return result, 200
        except ValidationError as e:
            return {"ok":False, "errors": e.errors()}, 400
        except Exception as e:
            log.info(traceback.format_exc())
            return {"error": str(e)}, 400



class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:project_id>",
            "<int:project_id>/<int:feedback_id>",
        ]
    )

    mode_handlers = {PROMPT_LIB_MODE: PromptLibAPI}
