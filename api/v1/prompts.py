import json
from flask import request, g
from pydantic import ValidationError
from typing import List
from sqlalchemy import or_

from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth
from ...models.all import Prompt, PromptVersion, PromptTag
from ...models.pd.create import PromptCreateModel
from ...models.pd.detail import PromptDetailModel, PromptVersionDetailModel
from ...models.pd.list import MultiplePromptListModel

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.create_utils import create_prompt
from ...utils.prompt_utils import list_prompts
from ...utils.prompt_utils_legacy import prompts_create_prompt


class ProjectAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api(
    #     {
    #         "permissions": ["models.prompts.prompts.list"],
    #         "recommended_roles": {
    #             c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #             c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #         },
    #     }
    # )
    def get(self, project_id):
        log.info("Getting all prompts for project %s", project_id)
        with_versions = request.args.get("versions", "").lower() == "true"
        prompts = self.module.get_all(project_id, with_versions)

        return prompts

    # @auth.decorators.check_api(
    #     {
    #         "permissions": ["models.prompts.prompts.create"],
    #         "recommended_roles": {
    #             c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #             c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #         },
    #     }
    # )
    def post(self, project_id):
        try:
            prompt = prompts_create_prompt(project_id, dict(request.json))
            return prompt, 201
        except ValidationError as e:
            return e.errors(), 400


class PromptLibAPI(api_tools.APIModeHandler):
    # def _get_project_id(self, project_id: int | None) -> int:
    #     if not project_id:
    #         project_id = 0  # todo: get user personal project id here
    #     return project_id

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
        # project_id = self._get_project_id(project_id)

        filters = []
        if tags := request.args.get('tags'):
            # # Filtering parameters
            # tags = request.args.getlist("tags", type=int)
            if isinstance(tags, str):
                tags = tags.split(',')
            filters.append(Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags))))

        if author_id := request.args.get('author_id'):
            filters.append(Prompt.versions.any(PromptVersion.author_id == author_id))

        if statuses := request.args.get('statuses'):
            statuses = statuses.split(',')
            filters.append(Prompt.versions.any(PromptVersion.status.in_(statuses)))

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
            project_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters
        )
        # parsing
        parsed = MultiplePromptListModel(prompts=prompts)

        return {
            "rows": [json.loads(i.json()) for i in parsed.prompts],
            "total": total
        },  200

    # @auth.decorators.check_api(
    #     {
    #         "permissions": ["models.prompt_lib.prompts.create"],
    #         "recommended_roles": {
    #             c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #             c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #         },
    #     }
    # )
    def post(self, project_id: int | None = None, **kwargs):
        # project_id = self._get_project_id(project_id)

        raw = dict(request.json)
        raw["owner_id"] = project_id
        author_id = auth.current_user().get("id")
        for version in raw.get("versions", []):
            version["author_id"] = author_id
        try:
            prompt_data = PromptCreateModel.parse_obj(raw)
        except ValidationError as e:
            return e.errors(), 400

        with db.with_project_schema_session(project_id) as session:
            prompt = create_prompt(prompt_data, session)
            session.commit()

            result = PromptDetailModel.from_orm(prompt)
            result.version_details = PromptVersionDetailModel.from_orm(
                prompt.versions[0]
            )

            return json.loads(result.json()), 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes(
        [
            "",
            "<int:project_id>",
        ]
    )

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
