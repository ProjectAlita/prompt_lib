from typing import List
from ...utils.constants import PROMPT_LIB_MODE

from flask import request, g
from tools import api_tools, config as c, db, auth
from pylon.core.tools import log
from pydantic import ValidationError
from ...models.pd.collections import CollectionListModel
from ...utils.collections import (
    list_collections,
    create_collection,
    PromptInaccessableError,
)

import json


class PromptLibAPI(api_tools.APIModeHandler):
    def _get_project_id(self, project_id: int | None) -> int:
        if not project_id:
            project_id = 0  # todo: get user personal project id here
        return project_id

    def get(self, project_id: int | None = None, **kwargs):
        project_id = self._get_project_id(project_id)
        # list prompts
        total, collections = list_collections(project_id, request.args)
        # parsing
        parsed: List[CollectionListModel] = []
        for col in collections:
            col_model = CollectionListModel.from_orm(col)
            col_model.author = auth.get_user(user_id=col_model.author_id)
            parsed.append(col_model)

        return {
            "rows": [json.loads(i.json(exclude={"author_id"})) for i in parsed],
            "total": total,
        }, 200

    def post(self, project_id: int | None = None, **kwargs):
        project_id = self._get_project_id(project_id)
        data = request.get_json()
        data["owner_id"], data["author_id"] = project_id, g.auth.id
        try:
            result = create_collection(self.module.context, project_id, data)
            return result, 201
        except ValidationError as e:
            return e.errors(), 400
        except PromptInaccessableError as e:
            return {"error": e.message}, 403


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "",
            "<int:project_id>",
        ]
    )

    mode_handlers = {
        # c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
