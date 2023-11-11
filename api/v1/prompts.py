from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from tools import api_tools, auth, config as c

from sqlalchemy.orm import joinedload
from ...models.pd.base import PromptTagBaseModel
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils_v1 import prompts_create_prompt


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompts.list"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id):
        log.info('Getting all prompts for project %s', project_id)
        with_versions = request.args.get('versions', '').lower() == 'true'
        prompts = self.module.get_all(project_id, with_versions)

        return prompts

    @auth.decorators.check_api({
        "permissions": ["models.prompts.prompts.create"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def post(self, project_id):
        try:
            prompt = prompts_create_prompt(project_id, dict(request.json))
            return prompt, 201
        except ValidationError as e:
            return e.errors(), 400


from flask import request, g
from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth

from pydantic import ValidationError
from ...models.all import Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag
from ...models.pd.create import PromptCreateModel
from ...models.pd.detail import PromptDetailModel, PromptVersionDetailModel
from ...models.pd.list import PromptListModel, PromptTagListModel
import json


class PromptLibAPI(api_tools.APIModeHandler):
    def get(self, project_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompts = session.query(Prompt).options(joinedload(Prompt.versions).joinedload(PromptVersion.tags)).all()

            parsed = []
            for i in prompts:
                p = PromptListModel.from_orm(i)
                tags = dict()
                for v in i.versions:
                    for t in v.tags:
                        tags[t.name] = PromptTagListModel.from_orm(t).dict()
                p.tags = list(tags.values())
                parsed.append(p)

            users = auth.list_users(user_ids=list(set(i.owner_id for i in parsed)))
            user_map = {i['id']: i for i in users}

            for i in parsed:
                i.owner = user_map[i.owner_id]

            return [json.loads(i.json()) for i in parsed], 200

    def post(self, project_id: int, **kwargs):
        raw = dict(request.json)
        raw['owner_id'] = g.auth.id
        try:
            prompt_data = PromptCreateModel.parse_obj(raw)
        except ValidationError as e:
            return e.errors(), 400

        with db.with_project_schema_session(project_id) as session:
            prompt = Prompt(**prompt_data.dict(
                exclude_unset=True,
                exclude={'versions'}
            ))

            for ver in prompt_data.versions:
                prompt_version = PromptVersion(**ver.dict(
                    exclude_unset=True,
                    exclude={'variables', 'messages', 'tags'}
                ))
                prompt_version.prompt = prompt

                if ver.variables:
                    for i in ver.variables:
                        prompt_variable = PromptVariable(**i.dict())
                        prompt_variable.prompt_version = prompt_version
                        session.add(prompt_variable)
                if ver.messages:
                    for i in ver.messages:
                        prompt_message = PromptMessage(**i.dict())
                        prompt_message.prompt_version = prompt_version
                        session.add(prompt_message)

                if ver.tags:
                    prompt_version.tags = []
                    existing_tags = session.query(PromptTag).filter(
                        PromptTag.name.in_({i.name for i in ver.tags})
                    ).all()
                    existing_tags_map = {i.name: i for i in existing_tags}
                    for i in ver.tags:
                        prompt_tag = existing_tags_map.get(i.name, PromptTag(**i.dict()))
                        prompt_version.tags.append(prompt_tag)

                session.add(prompt_version)
            session.add(prompt)
            session.commit()

            result = PromptDetailModel.from_orm(prompt)
            result.latest = PromptVersionDetailModel.from_orm(prompt.versions[0])
            result.latest.author = auth.get_user(user_id=prompt.owner_id)
            return json.loads(result.json()), 201


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
