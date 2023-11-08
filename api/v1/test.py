from typing import Optional, List

from flask import request, g
from pylon.core.tools import web, log
from tools import api_tools, config as c, db

from pydantic import BaseModel, ValidationError, validator
from ...models.all import Prompt, PromptVersion, PromptVariable, PromptMessage, PromptTag
from ...models.enums.all import PromptVersionType, MessageRoles


class PromptTagCreateModel(BaseModel):
    name: str
    data: Optional[dict]


class PromptMessageCreateModel(BaseModel):
    role: MessageRoles
    name: Optional[str]
    content: Optional[str]
    custom_content: Optional[dict]


class PromptVariableCreateModel(BaseModel):
    name: str
    value: Optional[str]


class PromptVersionCreateModel(BaseModel):
    name: str
    commit_message: Optional[str]
    context: Optional[str]
    embedding_settings: Optional[dict]
    variables: Optional[List[PromptVariableCreateModel]]
    messages: Optional[List[PromptMessageCreateModel]]
    author_id: int
    tags: Optional[List[PromptTagCreateModel]]
    model_settings: Optional[dict]  # todo: create model for this field
    type: PromptVersionType = PromptVersionType.chat


class PromptCreateModel(BaseModel):
    name: str
    description: Optional[str]
    owner_id: int
    versions: Optional[List[PromptVersionCreateModel]]

    @validator('versions', pre=True)
    def set_author_from_owner(cls, value, values):
        log.info('validator==============')
        log.info(value)
        log.info(values)
        if 'author_id' not in value:
            for version in value:
                version['author_id'] = values.get('owner_id')
        return value



class API(api_tools.APIBase):
    url_params = [
        '<int:project_id>',
    ]

    def get(self, project_id: int, **kwargs):
        return [], 200

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
                        PromptTag.name.in_([i.name for i in ver.tags])
                    ).all()
                    existing_tags_names = set(i.name for i in existing_tags)
                    for i in [t for t in ver.tags if t.name not in existing_tags_names]:
                        prompt_tag = PromptTag(**i.dict())
                        prompt_version.tags.append(prompt_tag)

                session.add(prompt_version)
            session.add(prompt)
            session.commit()

            result = prompt.to_json()
            result['versions'] = []
            for v in prompt.versions:
                v_data = v.to_json()
                v_data['variables'] = []
                for i in v.variables:
                    v_data['variables'].append(i.to_json())
                v_data['messages'] = []
                for i in v.messages:
                    v_data['messages'].append(i.to_json())
                for i in v.tags:
                    v_data['tags'].append(i.to_json())
                result['versions'].append(v_data)
            return result, 201
