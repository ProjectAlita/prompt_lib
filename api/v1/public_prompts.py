import json
from flask import request, g
from typing import List
from sqlalchemy import or_

from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth
from ...models.all import Prompt, PromptVersion, PromptTag
from ...models.pd.list import MultiplePublishedPromptListModel
from ...models.enums.all import PromptVersionStatus

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils import list_prompts
from ...utils.utils import add_public_project_id


class PromptLibAPI(api_tools.APIModeHandler):
    @add_public_project_id
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.public_prompts.list"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def get(self, *, project_id, **kwargs):
        ai_project_id = project_id
        filters = [Prompt.versions.any(PromptVersion.status == PromptVersionStatus.published)]

        if tags := request.args.get('tags'):
            # # Filtering parameters
            # tags = request.args.getlist("tags", type=int)
            if isinstance(tags, str):
                tags = tags.split(',')
            filters.append(Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags))))

        if author_id := request.args.get('author_id'):
            filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))

        # Search parameters
        if search := request.args.get('query'):
            filters.append(
                or_(
                    Prompt.name.ilike(f"%{search}%"),
                    Prompt.description.ilike(f"%{search}%")
                )
            )

        # Pagination parameters
        limit = request.args.get("limit", default=10, type=int)
        offset = request.args.get("offset", default=0, type=int)

        # Sorting parameters
        sort_by = request.args.get("sort_by", default="created_at")
        sort_order = request.args.get("sort_order", default="desc")

        # list prompts
        total, prompts = list_prompts(
            project_id=ai_project_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters
        )
        # parsing
        parsed = MultiplePublishedPromptListModel(prompts=prompts)

        return {
            "rows": [json.loads(i.json(exclude={"status"})) for i in parsed.prompts],
            "total": total
        }, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "",
        ]
    )

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
