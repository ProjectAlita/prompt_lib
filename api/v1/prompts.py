import json

from flask import request
from pydantic import ValidationError

from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth

from ...models.enums.events import PromptEvents
from ...models.pd.misc import MultiplePromptListModel
from ...models.pd.prompt import PromptDetailModel, PromptCreateModel
from ...models.pd.prompt_version import PromptVersionDetailModel
from ...models.pd.search import SearchDataModel

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.create_utils import create_prompt
from ...utils.prompt_utils import list_prompts_api
from ...utils.prompt_utils_legacy import prompts_create_prompt


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompts.prompts.list"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    def get(self, project_id):
        # log.info("Getting all prompts for project %s", project_id)
        with_versions = request.args.get("versions", "").lower() == "true"
        prompts = self.module.get_all(project_id, with_versions)

        return prompts

    @auth.decorators.check_api(
        {
            "permissions": ["models.prompts.prompts.create"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    def post(self, project_id):
        try:
            prompt = prompts_create_prompt(project_id, dict(request.json))
            return prompt, 201
        except ValidationError as e:
            return e.errors(), 400


class PromptLibAPI(api_tools.APIModeHandler):

    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.prompts.list"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def get(self, project_id: int | None = None, **kwargs):
        try:
            payload = request.get_json()
            search_data = payload.get("search_data")
            SearchDataModel.validate(search_data)
        except Exception:
            search_data = None
        
        collection = {
            "id": request.args.get('collection_id', type=int),
            "owner_id": request.args.get('collection_owner_id', type=int)
        }
        some_result = list_prompts_api(
            project_id=project_id,
            tags=request.args.get('tags'),
            author_id=request.args.get('author_id'),
            q=request.args.get('query'),
            limit=request.args.get("limit", default=None,),
            offset=request.args.get("offset", default=0, type=int),
            sort_by=request.args.get("sort_by", default="created_at"),
            sort_order=request.args.get("sort_order", default='desc'),
            my_liked=request.args.get('my_liked', False),
            trend_start_period=request.args.get('trend_start_period'),
            trend_end_period=request.args.get('trend_end_period'),
            statuses=request.args.get('statuses'),
            collection=collection,
            search_data=search_data
        )
        parsed = MultiplePromptListModel(prompts=some_result['prompts'])
        return {
            'total': some_result['total'],
            'rows': [
                json.loads(i.json())
                for i in parsed.prompts
            ]
        }, 200

    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.prompts.create"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def post(self, project_id: int | None = None, **kwargs):
        # create prompt
        raw = dict(request.json)
        raw["owner_id"] = project_id
        author_id = auth.current_user().get("id")
        for version in raw.get("versions", []):
            version["author_id"] = author_id
        try:
            prompt_data = PromptCreateModel.parse_obj(raw)
        except ValidationError as e:
            return e.errors(), 400

        with db.get_session(project_id) as session:
            prompt = create_prompt(prompt_data, session)
            session.commit()

            result = PromptDetailModel.from_orm(prompt)
            result.version_details = PromptVersionDetailModel.from_orm(
                prompt.versions[0]
            )

            result = json.loads(result.json())
            self.module.context.event_manager.fire_event(
                PromptEvents.prompt_change, result
            )

            return result, 201


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
