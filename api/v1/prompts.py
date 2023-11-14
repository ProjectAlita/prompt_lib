from sqlalchemy.orm import joinedload
from ...models.pd.base import PromptTagBaseModel
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils_legacy import prompts_create_prompt
from flask import request, g
from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth

from pydantic import ValidationError
from ...models.all import Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag
from ...models.pd.create import PromptCreateModel
from ...models.pd.detail import PromptDetailModel, PromptVersionDetailModel
from ...models.pd.list import PromptListModel, PromptTagListModel
import json


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


class PromptLibAPI(api_tools.APIModeHandler):

    def _get_project_id(self, project_id: int | None) -> int:
        if not project_id:
            project_id = 0  # todo: get user personal project id here
        return project_id

    def get(self, project_id: int | None = None, **kwargs):
        project_id = self._get_project_id(project_id)

        with db.with_project_schema_session(project_id) as session:
            prompts: list[Prompt] = session.query(Prompt).options(
                joinedload(Prompt.versions).joinedload(PromptVersion.tags)).all()

            all_authors = set()
            parsed: list[PromptListModel] = []
            for i in prompts:
                p = PromptListModel.from_orm(i)
                # p.author_ids = set()
                tags = dict()
                for v in i.versions:
                    for t in v.tags:
                        tags[t.name] = PromptTagListModel.from_orm(t).dict()
                    p.author_ids.add(v.author_id)
                    all_authors.update(p.author_ids)
                p.tags = list(tags.values())
                parsed.append(p)
            users = auth.list_users(user_ids=list(all_authors))
            user_map = {i['id']: i for i in users}

            for i in parsed:
                i.set_authors(user_map)

            return [json.loads(i.json(exclude={'author_ids'})) for i in parsed], 200

    def post(self, project_id: int | None = None, **kwargs):
        project_id = self._get_project_id(project_id)

        raw = dict(request.json)
        raw['owner_id'] = project_id
        for version in raw.get('versions', []):
            version['author_id'] = g.auth.id
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
            result.latest.author = auth.get_user(user_id=result.latest.author_id)
            return json.loads(result.json()), 201


def with_modes(url_params: list[str]) -> list:
    params = set()
    for i in url_params:
        if not i.startswith('<string:mode>'):
            if i == '':
                params.add('<string:mode>')
            else:
                params.add(f'<string:mode>/{i}')
        params.add(i)
    return list(params)
#
#
# log.info('with_modes')
# log.info(with_modes([
#     '<string:mode>/<int:project_id>',
#     '<int:project_id>',
#
#     ''
# ]))


class API(api_tools.APIBase):
    url_params = with_modes([
        '',
        '<int:project_id>',
    ])

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
        PROMPT_LIB_MODE: PromptLibAPI,
    }
