from flask import request, g
from pylon.core.tools import web, log
from tools import api_tools, config as c, db, auth

from pydantic import ValidationError
from ...models.all import Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag
from ...models.pd.create import PromptCreateModel
from ...models.pd.detail import PromptDetailModel, PromptVersionDetailModel
from ...models.pd.list import PromptListModel
import json


class API(api_tools.APIBase):
    url_params = [
        '<int:project_id>',
        '<string:mode>/<int:project_id>',
    ]

    def get(self, project_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            prompts = session.query(Prompt).all()
            parsed = [PromptListModel.from_orm(i) for i in prompts]
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
            log.info(result)
            return json.loads(result.json()), 201
