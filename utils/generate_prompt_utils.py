import json
from typing import List

from pylon.core.tools import log

from ..models.pd.predict import PromptVersionPredictModel


def get_generated_prompt_content(payload: PromptVersionPredictModel, conversation: List[dict]):
    from tools import worker_client  # pylint: disable=E0401,C0415
    try:
        result = worker_client.chat_model_invoke(
            integration_name=payload.integration.name,
            settings=payload,
            messages=conversation,
        )
        log.info(f'{result=}')
    except Exception as e:
        return {'error': str(e)}, 400
    return json.loads(result.get('content'))
