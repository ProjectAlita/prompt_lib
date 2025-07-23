import json
import traceback
from uuid import uuid4
from typing import Optional

from pydantic.v1 import ValidationError
from tools import db, auth, serialize
from pylon.core.tools import web, log

from ..models.enums.all import PromptVersionType
from ..models.pd.predict import PromptVersionPredictModel
from ..utils.conversation import prepare_payload, convert_messages_to_langchain, prepare_conversation, \
    CustomTemplateError
from ...promptlib_shared.utils.constants import PredictionEvents
from ...promptlib_shared.utils.sio_utils import SioValidationError, get_event_room, SioEvents


class RPC:
    @web.rpc("prompt_lib_predict_sio", "predict_sio")
    def predict_sio(self,
                    sid: str | None,
                    data: dict,
                    sio_event: str = SioEvents.promptlib_predict.value,
                    start_event_content: Optional[dict] = None,
                    chat_project_id: Optional[int] = None,
                    **kwargs
                    ):
        #
        if start_event_content is None:
            start_event_content = {}
        #
        data['message_id'] = data.get('message_id', str(uuid4()))
        data['stream_id'] = data.get('stream_id', data['message_id'])
        #
        try:
            payload: PromptVersionPredictModel = prepare_payload(data=data)
        except ValidationError as e:
            raise SioValidationError(
                sio=self.context.sio,
                sid=sid,
                event=sio_event,
                error=e.errors(),
                stream_id=data.get("stream_id"),
                message_id=data.get("message_id")
            )
        #
        try:
            conversation = prepare_conversation(payload=payload)
        except CustomTemplateError as e:
            raise SioValidationError(
                sio=self.context.sio,
                sid=sid,
                event=sio_event,
                error=e.errors(),
                stream_id=payload.stream_id,
                message_id=payload.message_id,
            )
        except Exception as e:
            log.exception("prepare_conversation")
            raise SioValidationError(
                sio=self.context.sio,
                sid=sid,
                event=sio_event,
                error={'ok': False, 'msg': str(e), 'loc': []},
                stream_id=payload.stream_id,
                message_id=payload.message_id
            )
        #
        room = get_event_room(
            event_name=sio_event,
            room_id=payload.stream_id
        )
        #
        if sid:
            self.context.sio.enter_room(sid, room)
        #
        self.context.sio.emit(
            event=sio_event,
            data={
                "stream_id": payload.stream_id,
                "message_id": payload.message_id,
                "type": "start_task",
                "message_type": payload.type,
                "content": {**start_event_content},
                'interaction_uuid': payload.interaction_uuid
            },
            room=room,
        )
        #
        full_result = ""
        #
        from tools import worker_client  # pylint: disable=E0401,C0415
        #
        try:
            token_limit, max_tokens = self.get_limits_from_payload(payload)  # pylint: disable=E1101
            conversation = worker_client.limit_tokens(
                data=conversation,
                token_limit=token_limit,
                max_tokens=max_tokens,
            )
            #
            for chunk in worker_client.chat_model_stream(
                integration_name=payload.integration.name,
                settings=payload,
                messages=conversation,
            ):
                full_result += chunk["content"]
                #
                chunk_data = {
                    "type": "AIMessageChunk",
                    "content": chunk["content"],
                    "response_metadata": {},
                }
                #
                chunk_data['stream_id'] = payload.stream_id
                chunk_data['message_id'] = payload.message_id
                #
                if payload.type == PromptVersionType.freeform:
                    chunk_data['message_type'] = PromptVersionType.freeform
                #
                self.context.sio.emit(
                    event=sio_event,
                    data=chunk_data,
                    room=room,
                )
        except BaseException as exception:  # pylint: disable=W0718
            log.debug("Predict exception: %s", traceback.format_exc())
            #
            exception_info = str(exception)
            #
            self.context.sio.emit(
                event=sio_event,
                data={
                    "type": "AIMessageChunk",
                    "content": f"⚠ Predict exception: {exception_info}",
                    "response_metadata": {},
                    "stream_id": payload.stream_id,
                    "message_id": payload.message_id,
                },
                room=room,
            )
        #
        self.context.sio.emit(
            event=sio_event,
            data={
                "type": "AIMessageChunk",
                "content": "",
                "response_metadata": {
                    "finish_reason": "stop",
                },
                "stream_id": payload.stream_id,
                "message_id": payload.message_id,
            },
            room=room,
        )
        #
        if sio_event == SioEvents.chat_predict.value and chat_project_id is not None:
            chat_payload = {
                'message_id': payload.message_id,
                'response_metadata': {
                    'project_id': payload.project_id,
                    'chat_project_id': chat_project_id,
                },
                'content': full_result,
            }
            self.context.event_manager.fire_event('chat_message_stream_end', chat_payload)
        #
        if sid:
            current_user = auth.current_user(
                auth_data=auth.sio_users[sid]
            )
        else:
            current_user = auth.current_user()
        #
        tokens_in = worker_client.ai_count_tokens(
            integration_name=payload.integration.name,
            settings=payload,
            data=full_result,
        )
        #
        tokens_out = worker_client.ai_count_tokens(
            integration_name=payload.integration.name,
            settings=payload,
            data=conversation,
        )
        #
        conversation = convert_messages_to_langchain(conversation)
        #
        event_payload = {
            'pylon': str(self.context.id),
            'project_id': payload.project_id,
            'chat_project_id': chat_project_id,
            'user_id': current_user["id"],
            'predict_source': str(sio_event),
            'entity_type': 'prompt',
            'entity_id': payload.prompt_id,
            'entity_meta': {'version_id': payload.prompt_version_id, 'prediction_type': payload.type},
            'chat_history': [i.dict() for i in conversation],
            'predict_response': full_result,
            'model_settings': payload.merged_settings,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'interaction_uuid': payload.interaction_uuid,
            'message_id': payload.message_id
        }
        #
        self.context.event_manager.fire_event(
            PredictionEvents.prediction_done,
            json.loads(json.dumps(event_payload))
        )

        return {"result": event_payload["predict_response"]}
