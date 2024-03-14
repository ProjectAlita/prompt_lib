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
from ..models.pd.predict import PromptVersionPredictStreamModel
from ..utils.ai_providers import AIProvider
from ..utils.conversation import prepare_payload, prepare_conversation, CustomTemplateError
from ...integrations.models.pd.integration import SecretField
from langchain_openai import AzureChatOpenAI


class SioEvents(str, Enum):
    promptlib_predict = 'promptlib_predict'


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

    @web.sio(SioEvents.promptlib_predict)
    def predict(self, sid, data):

        try:
            payload = prepare_payload(data=data, pd_model=PromptVersionPredictStreamModel)
        except ValidationError as e:
            return e.errors()

        try:
            conversation = prepare_conversation(payload=payload)
        except CustomTemplateError as e:
            return e.errors()
        except Exception as e:
            log.exception("prepare_conversation")
            return {'ok': False, 'msg': str(e), 'loc': []}

        log.info(f'{conversation=}')

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

        integration = AIProvider.get_integration(
            project_id=payload.project_id,
            integration_uid=payload.model_settings.model.integration_uid,
        )
        settings = {**integration.settings, **payload.model_settings.merged}
        log.info(f'{settings=}')
        api_token = SecretField.parse_obj(settings["api_token"])
        try:
            api_token = api_token.unsecret(integration.project_id)
        except AttributeError:
            api_token = api_token.unsecret(None)

        chat = AzureChatOpenAI(
            api_key=api_token,
            azure_endpoint=settings['api_base'],
            azure_deployment=settings['name'],
            api_version=settings['api_version'],
            streaming=True
        )
        for chunk in chat.stream(input=conversation, config=settings):
            data = chunk.dict()
            data['stream_id'] = stream_id
            if payload.type == PromptVersionType.freeform:
                data['message_type'] = PromptVersionType.freeform
            self.context.sio.emit(
                event=SioEvents.promptlib_predict,
                data=data,
                room=room,
            )
