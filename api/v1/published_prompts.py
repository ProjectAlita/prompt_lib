import json
from flask import request, g
from pydantic import ValidationError
from typing import List

from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth
from ...models.all import Prompt, PromptVersion, PromptTag
from ...models.pd.list import PromptTagListModel, PublishedPromptListModel
from ...models.enums.all import PromptVersionStatus

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils import list_prompts, is_personal_project



class PromptLibAPI(api_tools.APIModeHandler):

    # @auth.decorators.check_api(
    #     {
    #         "permissions": ["models.prompt_lib.prompts.list"],
    #         "recommended_roles": {
    #             c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #             c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #         },
    #     }
    # )
    def get(self, project_id: int | None = None, **kwargs):
        filters = []
        if not is_personal_project(project_id):
            filters.append(Prompt.versions.any(PromptVersion.status == PromptVersionStatus.published))
        if tags := request.args.get('tags'):
            # # Filtering parameters
            # tags = request.args.getlist("tags", type=int)
            if isinstance(tags, str):
                tags = tags.split(',')
            filters.append(Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags))))

        # Pagination parameters
        limit = request.args.get("limit", default=10, type=int)
        offset = request.args.get("offset", default=0, type=int)

        # Sorting parameters
        sort_by = request.args.get("sort_by", default="created_at")
        sort_order = request.args.get("sort_order", default="desc")

        # list prompts
        total, prompts = list_prompts(
            project_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters
        )
        # parsing
        all_authors = set()
        parsed: List[PublishedPromptListModel] = []
        for i in prompts:
            p = PublishedPromptListModel.from_orm(i)
            # p.author_ids = set()
            tags = dict()
            version_statuses = set()
            for v in i.versions:
                for t in v.tags:
                    tags[t.name] = PromptTagListModel.from_orm(t).dict()
                p.author_ids.add(v.author_id)
                version_statuses.add(v.status)
                all_authors.update(p.author_ids)
            p.tags = list(tags.values())
            p.version_statuses = version_statuses
            parsed.append(p)

        users = auth.list_users(user_ids=list(all_authors))
        user_map = {i["id"]: i for i in users}

        for i in parsed:
            i.set_authors(user_map)

        return {
            "rows": [json.loads(i.json(exclude={"author_ids"})) for i in parsed],
            "total": total
        },  200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "",
            "<int:project_id>",
        ]
    )

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
