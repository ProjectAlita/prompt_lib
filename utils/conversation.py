from typing import List

from jinja2 import TemplateSyntaxError, Environment, DebugUndefined

from ..models.enums.all import MessageRoles
from ..models.pd.predict import PromptVersionPredictModel, PromptMessagePredictModel
from tools import db
from pylon.core.tools import log


def _resolve_variables(text, vars) -> str:
    environment = Environment(undefined=DebugUndefined)
    ast = environment.parse(text)
    template = environment.from_string(text)
    return template.render(vars)


def prepare_payload(data: dict) -> PromptVersionPredictModel:
    data['integration'] = {}
    payload = PromptVersionPredictModel.parse_obj(data)
    log.debug(f'{payload=}')
    return payload


class CustomTemplateError(Exception):
    def __init__(self, msg: str, loc: list):
        self.msg = msg
        self.type = 'CustomTemplateError'
        self.loc = loc
        super().__init__(self.msg)

    def errors(self) -> List[dict]:
        return [{'ok': False, 'msg': self.msg, 'type': self.type, 'loc': self.loc}]


def prepare_conversation(payload: PromptVersionPredictModel, skip_validation_error: bool = True) -> List[dict]:
    variables = {v.name: v.value for v in payload.variables}
    messages = []

    if payload.context:
        try:
            messages.append(
                PromptMessagePredictModel(
                    role=MessageRoles.system,
                    content=_resolve_variables(
                        payload.context,
                        variables
                    )
                ).dict(exclude_unset=True)
            )
        except TemplateSyntaxError:
            if skip_validation_error:
                messages.append(
                    PromptMessagePredictModel(
                        role=MessageRoles.system,
                        content=payload.context,
                    ).dict(exclude_unset=True)
                )
            else:
                raise CustomTemplateError(msg='Context template error', loc=['context'])

    for idx, i in enumerate(payload.messages):
        message = i.dict(exclude={'content'}, exclude_none=True, exclude_unset=True)
        try:
            message['content'] = _resolve_variables(i.content, variables)
        except TemplateSyntaxError:
            if skip_validation_error:
                message['content'] = i.content
            else:
                raise CustomTemplateError(msg='Message template error', loc=['messages', idx])
        messages.append(message)

    if payload.chat_history:
        for i in payload.chat_history:
            messages.append(i.dict(exclude_unset=True))

    if payload.user_input:
        messages.append(
            PromptMessagePredictModel(
                role=MessageRoles.user,
                content=payload.user_input,
                name=payload.user_name
            ).dict(exclude_unset=True, exclude_none=True)
        )
    return messages


def convert_messages_to_langchain(messages: list) -> list:
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
    )

    new_conversation = []
    for item in messages:
        if item["role"] == MessageRoles.assistant:
            new_conversation.append(AIMessage(
                content=item["content"],
                name=item.get("name", None),
            ))
        elif item["role"] == MessageRoles.user:
            new_conversation.append(HumanMessage(
                content=item["content"],
                name=item.get("name", None),
            ))
        elif item["role"] == MessageRoles.system:
            new_conversation.append(SystemMessage(
                content=item["content"],
                name=item.get("name", None),
            ))
    return new_conversation
