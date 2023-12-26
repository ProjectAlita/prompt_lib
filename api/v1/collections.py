from typing import List
from ...utils.constants import PROMPT_LIB_MODE

from flask import request, g
from tools import api_tools, config as c, db, auth
from pylon.core.tools import log
from pydantic import ValidationError
from ...models.pd.collections import CollectionListModel
from ...utils.collections import (
    get_collection_tags,
    list_collections,
    create_collection,
    get_detail_collection,
    PromptInaccessableError,
)

import json

from ...utils.utils import get_authors_data


def populate_inlcude_prompt_flag(collection, prompt_id, prompt_owner_id):
    for prompt in collection.prompts:
        if int(prompt['owner_id']) == int(prompt_owner_id) and \
            int(prompt['id']) == int(prompt_id):
            collection.includes_prompt = True
            break
    else:
        collection.includes_prompt = False


class PromptLibAPI(api_tools.APIModeHandler):
    # def _get_project_id(self, project_id: int | None) -> int:
    #     if not project_id:
    #         project_id = 0  # todo: get user personal project id here
    #     return project_id

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.collections.list"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id: int | None = None, **kwargs):
        # project_id = self._get_project_id(project_id)
        # list prompts
        prompt_id = request.args.get('prompt_id')
        prompt_owner_id = request.args.get('prompt_owner_id')
        need_tags = 'no_tags' not in request.args
        total, collections = list_collections(project_id, request.args)
        # parsing
        parsed: List[CollectionListModel] = []
        users = get_authors_data([i.author_id for i in collections])
        user_map = {i['id']: i for i in users}
        for col in collections:
            col_model = CollectionListModel.from_orm(col)
            col_model.author = user_map.get(col_model.author_id)
            if need_tags:
                col_model.tags = get_collection_tags(col.prompts)
            
            if prompt_id and prompt_owner_id:
                populate_inlcude_prompt_flag(col_model, prompt_id, prompt_owner_id)
            parsed.append(col_model)

        return {
            "rows": [json.loads(i.json(exclude={"author_id"})) for i in parsed],
            "total": total,
        }, 200

    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.collections.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def post(self, project_id: int | None = None, **kwargs):
        # project_id = self._get_project_id(project_id)
        data = request.get_json()

        author_id = auth.current_user().get("id")
        data["owner_id"], data["author_id"] = project_id, author_id

        try:
            new_collection = create_collection(project_id, data)
            result = get_detail_collection(new_collection)
            return result, 201
        except ValidationError as e:
            return e.errors(), 400
        except PromptInaccessableError as e:
            return {"error": e.message}, 403


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            # "",
            "<int:project_id>",
        ]
    )

    mode_handlers = {
        # c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
