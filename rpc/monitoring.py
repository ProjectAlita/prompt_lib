from pylon.core.tools import web, log

from tools import db

from ..models.all import Prompt
from ...promptlib_shared.utils.sio_utils import SioEvents


class RPC:
    @web.rpc('prompt_lib_is_first_message_to_prompt')
    def is_first_message_to_prompt(self, project_id: int | None, prompt_id: int | None, predict_source: str | None,
                                   chat_history: list = None, entity_meta: dict = None) -> bool:
        if entity_meta is None:
            entity_meta = {}
        if chat_history is None:
            chat_history = []

        if prompt_id is None:
            # predict without prompt id
            log.info('return False - predict without prompt id')
            return False
        else:
            from ...prompt_lib.models.enums.all import PromptVersionType
            prediction_type = entity_meta.get('prediction_type', PromptVersionType.chat)
            if prediction_type == PromptVersionType.freeform:
                # is completion prompt
                log.info('return True - is completion prompt')
                return True

        # todo: handle application predicts for prompt tools

        with db.get_session(project_id) as session:
            if predict_source in (SioEvents.chat_predict,):
                # not handling prompt usage in chats
                raise NotImplementedError
            else:
                if len(chat_history) == 0:
                    log.info('return True - chat history is empty')
                    return True
                else:
                    for i in reversed(chat_history):
                        if i.get('role', i.get('type')) in {'assistant', 'ai'}:
                            from ...prompt_lib.models.all import PromptVersion
                            flt = [PromptVersion.prompt_id == prompt_id]
                            prompt_version_id = entity_meta.get('version_id')
                            if prompt_version_id:
                                flt.append(PromptVersion.id == prompt_version_id)
                            else:
                                flt.append(PromptVersion.name == 'latest')

                            prompt_version: PromptVersion = session.query(PromptVersion).where(*flt).first()
                            if prompt_version is None:
                                raise ValueError(f'Prompt version not found with [{flt}]')
                            prompt_version_wm = prompt_version.welcome_message
                            log.info(f'{prompt_version_wm=}, {i=}')
                            if i.get('content') == prompt_version_wm:
                                log.info(
                                    f"return {i.get('content') == prompt_version_wm} - last assistant message compared to welcome message"
                                )
                                return True
                            else:
                                message_in_messages = i.get('content') in {i.content for i in
                                                                           prompt_version.messages}
                                log.info(
                                    f"return {message_in_messages} - checked message is{'' if message_in_messages else 'NOT'} in examples"
                                )
                                return message_in_messages
            log.info('return True - no assistant messages in chat history')
            return True

    @web.rpc(f'prompt_lib_get_prompt_count', "get_prompt_count")
    def prompt_lib_get_prompt_count(self, project_id: int, **kwargs) -> int:
        with db.get_session(project_id) as session:
            return session.query(Prompt).count()
