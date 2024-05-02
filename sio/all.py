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
from queue import Empty

from pylon.core.tools import log, web  # pylint: disable=E0611,E0401,W0611

from ...promptlib_shared.utils.sio_utils import SioEvents, get_event_room

try:
    from langchain_openai import AzureChatOpenAI
except:
    from langchain.chat_models import AzureChatOpenAI


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
        self.predict_sio(
            sid, data, SioEvents.promptlib_predict
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
