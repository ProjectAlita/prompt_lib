#!/usr/bin/python3
# coding=utf-8

#   Copyright 2024 EPAM Systems
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

""" SIO """

import uuid
from enum import Enum

from pylon.core.tools import log, web  # pylint: disable=E0611,E0401,W0611

from pydantic import ValidationError
from ..models.enums.all import PromptVersionType
from ..utils.conversation import prepare_payload, prepare_conversation, CustomTemplateError
from ...integrations.models.pd.integration import SecretField
try:
    from langchain_openai import AzureChatOpenAI
except:
    from langchain.chat_models import AzureChatOpenAI


class SioEvents(str, Enum):
    promptlib_predict = 'promptlib_predict'
    promptlib_leave_rooms = 'promptlib_leave_rooms'


class SioValidationError(Exception):
    def __init__(self, sio, sid, event: SioEvents, error, stream_id: str):
        self.sio = sio
        self.type = 'error'
        self.event = event
        self.error = error
        self.stream_id = stream_id
        self.sid = sid
        self.room = get_event_room(
            event_name=SioEvents.promptlib_predict,
            room_id=stream_id
        )
        self.enter_room()
        self.emit_error()
        super().__init__(error)

    def enter_room(self) -> None:
        self.sio.enter_room(self.sid, self.room)

    def emit_error(self) -> None:
        self.sio.emit(
            event=self.event,
            data={
                'content': self.error,
                'type': self.type,
                'stream_id': self.stream_id
            },
            room=self.room,
        )


def get_event_room(event_name: SioEvents, room_id: uuid) -> str:
    return f'room_{event_name.value}_{room_id}'


class SIO:  # pylint: disable=E1101,R0903
    """
        SIO Resource

        self is pointing to current Module instance

        web.sio decorator takes one argument: event name
        Note: web.sio decorator must be the last decorator (at top)

        SIO resources use sio_check auth decorator
        auth.decorators.sio_check takes the following arguments:
        - permissions
        - scope_id=1
    """

    # Refactored predict method with enhanced error handling and conversation processing
    @web.sio(SioEvents.promptlib_predict)
    def predict(self, sid, data):
        # Implementation of the refactored method will be added here

        log.info(f'{conversation=}')
        log.info(f'{payload.merged_settings=}')
        api_token = SecretField.parse_obj(payload.merged_settings["api_token"])
        try:
            api_token = api_token.unsecret(payload.integration.project_id)
        except AttributeError:
            api_token = api_token.unsecret(None)

        try:
            chat = AzureChatOpenAI(
                api_key=api_token,
                azure_endpoint=payload.merged_settings['api_base'],
                azure_deployment=payload.merged_settings['model_name'],
                api_version=payload.merged_settings['api_version'],
                streaming=True
            )
        except:
            chat = AzureChatOpenAI(
                openai_api_key=api_token,
                openai_api_base=payload.merged_settings['api_base'],
                deployment_name=payload.merged_settings['model_name'],
                openai_api_version=payload.merged_settings['api_version'],
                streaming=True
            )
            #
            from langchain.schema import (
                AIMessage,
                HumanMessage,
                SystemMessage,
            )
            from ..models.enums.all import MessageRoles
            #
            new_conversation = conversation
            conversation = []
            #
            for item in new_conversation:
                if item["role"] == MessageRoles.assistant:
                    conversation.append(AIMessage(content=item["content"]))
                elif item["role"] == MessageRoles.user:
                    conversation.append(HumanMessage(content=item["content"]))
                elif item["role"] == MessageRoles.system:
                    conversation.append(SystemMessage(content=item["content"]))

        stream_id = payload.message_id
        room = get_event_room(
            event_name=SioEvents.promptlib_predict,
            room_id=stream_id
        )
        self.context.sio.enter_room(sid, room)
        self.context.sio.emit(
            event=SioEvents.promptlib_predict,
            data={
                "stream_id": stream_id,
                "type": "start_task",
                "message_type": payload.type
            },
            room=room,
        )
        for chunk in chat.stream(input=conversation, config=payload.merged_settings):
            data = chunk.dict()
            data['stream_id'] = stream_id
            if payload.type == PromptVersionType.freeform:
                data['message_type'] = PromptVersionType.freeform
            self.context.sio.emit(
                event=SioEvents.promptlib_predict,
                data=data,
                room=room,
            )

    @web.sio(SioEvents.promptlib_leave_rooms)
    def leave_room_prompt_lib(self, sid, data):
        for room_id in data:
            room = get_event_room(
                event_name=SioEvents.promptlib_predict,
                room_id=room_id
            )
            self.context.sio.leave_room(sid, room)


# s = useSocket('leave_room')
# s.emit([123,456,678])
#
#
# s = useSocket('leave_room')
# s.emit({'event_name': 'promptlib_predict', 'stream_ids': [123,456,678]})
#
#
#
# s = useSocket('leave_room_prompts')
# s.emit([123,456,678])
# s = useSocket('leave_room_datasources')
# s.emit([123,456,678])