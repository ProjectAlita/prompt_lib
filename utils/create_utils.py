from ..models.all import PromptVersion, PromptVariable, Prompt, PromptMessage
from ..models.pd.base import PromptVariableBaseModel, PromptMessageBaseModel, PromptTagBaseModel
from ..models.pd.create import PromptCreateModel, PromptVersionCreateModel, PromptVersionLatestCreateModel
from typing import Generator, List
from jinja2 import Environment, DebugUndefined, meta

from ...promptlib_shared.models.all import Tag


def create_variable(
        variable_data: PromptVariableBaseModel,
        prompt_version: PromptVersion | None = None,
        session=None
) -> PromptVariable:
    prompt_variable = PromptVariable(**variable_data.dict())
    if prompt_version:
        prompt_variable.prompt_version = prompt_version
    if session:
        session.add(prompt_variable)
    return prompt_variable


def create_variables(
        variables: List[PromptVariableBaseModel] | None,
        prompt_version: PromptVersion | None = None,
        session=None
) -> None:
    if variables:
        for i in variables:
            create_variable(i, prompt_version=prompt_version, session=session)


def create_message(
        message_data: PromptMessageBaseModel,
        prompt_version: PromptVersion | None = None,
        session=None
) -> PromptMessage:
    prompt_message = PromptMessage(**message_data.dict())
    if prompt_version:
        prompt_message.prompt_version = prompt_version
    if session:
        session.add(prompt_message)
    return prompt_message


def create_messages(
        messages: List[PromptMessageBaseModel] | None,
        prompt_version: PromptVersion | None = None,
        session=None
) -> None:
    if messages:
        for i in messages:
            create_message(i, prompt_version=prompt_version, session=session)


def get_existing_tags(
        tags: List[PromptTagBaseModel],
        session=None,
        project_id: int | None = None
) -> dict[str, Tag]:
    assert session or project_id, 'session or project_id is required'
    if not session and project_id:
        from tools import db
        with db.with_project_schema_session(project_id) as project_session:
            existing_tags: List[Tag] = project_session.query(Tag).filter(
                Tag.name.in_({i.name for i in tags})
            ).all()
    else:
        existing_tags: List[Tag] = session.query(Tag).filter(
            Tag.name.in_({i.name for i in tags})
        ).all()
    return {i.name: i for i in existing_tags}


def generate_tags(
        tags: List[PromptTagBaseModel],
        existing_tags_map: dict[str, Tag]
) -> Generator[Tag, None, None]:
    for i in tags:
        yield existing_tags_map.get(i.name, Tag(**i.dict()))


def find_vars_from_context(version):
    environment = Environment(undefined=DebugUndefined)
    ast = environment.parse(version.context)
    version_vars = [] if not version.variables else version.variables
    context_vars = set(meta.find_undeclared_variables(ast))
    version_vars = set(var.name for var in version_vars)
    empty_vars = context_vars - version_vars
    return [PromptVariableBaseModel(name=var) for var in empty_vars]
    

def create_version(
        version_data: PromptVersionCreateModel | PromptVersionLatestCreateModel,
        prompt: Prompt | None = None,
        session=None
) -> PromptVersion:
    prompt_version = PromptVersion(**version_data.dict(
        exclude_unset=True,
        exclude={'variables', 'messages', 'tags'}
    ))
    if prompt:
        prompt_version.prompt = prompt

    variables = find_vars_from_context(version_data)
    if version_data.variables:
        version_data.variables.extend(variables)
    else:
        version_data.variables = variables

    create_variables(version_data.variables, prompt_version=prompt_version, session=session)
    create_messages(version_data.messages, prompt_version=prompt_version, session=session)
    if version_data.tags:
        project_id = None
        if prompt:
            project_id = prompt.owner_id
        existing_tags_map = get_existing_tags(version_data.tags, session=session, project_id=project_id)
        prompt_version.tags = list(generate_tags(
            version_data.tags,
            existing_tags_map=existing_tags_map
        ))
    if session:
        session.add(prompt_version)
    return prompt_version


def create_prompt(prompt_data: PromptCreateModel, session=None) -> Prompt:
    prompt = Prompt(
        **prompt_data.dict(exclude_unset=True, exclude={"versions"})
    )

    for ver in prompt_data.versions:
        create_version(ver, prompt=prompt, session=session)
    if session:
        session.add(prompt)
    return prompt
