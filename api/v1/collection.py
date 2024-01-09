import traceback
from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from ...models.pd.collections import CollectionUpdateModel, CollectionPatchModel
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.collections import (
    delete_collection,
    update_collection,
    get_collection,
    patch_collection,
    PromptDoesntExist,
    PromptInaccessableError,
)

from tools import api_tools, auth, config as c


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.collection.details"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, collection_id: int):
        result = get_collection(project_id, collection_id)
        if not result:
            return {"error": f"No collection found with id '{collection_id}'"}, 404
        return result, 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.collection.delete"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def delete(self, project_id, collection_id):
        is_deleted = delete_collection(project_id, collection_id)
        return "", 204 if is_deleted else 404

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.collection.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def put(self, project_id, collection_id):
        try:
            payload = request.get_json()
            CollectionUpdateModel.validate(payload)
            result = update_collection(project_id, collection_id, payload)
            if not result:
                return {"error": f"No collection found with id '{collection_id}'"}, 404
            return result, 200
        except ValidationError as e:
            return e.errors(), 400
        except Exception as e:
            log.info(traceback.format_exc())
            return {"error": str(e)}, 400

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.collection.update"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def patch(self, project_id, collection_id):
        try:
            payload = request.get_json()
            collection_data = CollectionPatchModel.validate(payload)
            result = patch_collection(project_id, collection_id, collection_data)
            if not result:
                return {"error": f"No collection found with id '{collection_id}'"}, 404
            return result, 200
        except ValidationError as e:
            return e.errors(), 400
        except PromptDoesntExist as e:
            return {"error": e.message}, 404
        except PromptInaccessableError as e:
            return {"error": e.message}, 403
        except Exception as e:
            log.info(traceback.format_exc())
            return {"error": str(e)}, 400


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "<int:project_id>",
            "<int:project_id>/<int:collection_id>",
        ]
    )

    mode_handlers = {PROMPT_LIB_MODE: PromptLibAPI}
