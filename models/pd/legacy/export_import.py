from typing import Optional, List

from pydantic import root_validator, BaseModel, Field
from .prompts_pd import PromptModel
from pylon.core.tools import log


class ModelSettingsExport(BaseModel):
    temperature: float = 1.0
    top_p: float = 0.8
    top_k: int = 40
    max_decode_steps: int = 256
    max_tokens: int = 7


class PromptExport(PromptModel):
    class Config:
        fields = {
            'context': 'prompt',
            'input': 'test_input',
            'prompt': {'exclude': True},
            'test_input': {'exclude': True},
            'project_id': {'exclude': True},
            # 'integration_id': {'exclude': True},
        }
        orm_mode = True
        allow_population_by_field_name = True
    prompt: Optional[str] = None
    context: str
    input: Optional[str]
    model_settings: Optional[ModelSettingsExport]
    # integration_id: Optional[int] = None

    def dict_flat(self, **kwargs) -> dict:
        d = self.dict(**kwargs)
        if d.get('model_settings'):
            settings = self.convert_to_max_tokens(d.pop('model_settings'))
            d.update(settings)
        return d

    def convert_to_max_tokens(self, settings):
        decode_steps = settings.pop('max_decode_steps', None)
        if decode_steps:
            settings['max_tokens'] = decode_steps
        return settings


class PromptImport(PromptExport):
    model_settings: Optional[dict] = {}
    variables: List[dict] = []

    @root_validator(pre=True)
    def set_model_settings(cls, values: dict) -> dict:
        values['max_decode_steps'] = values['max_tokens']
        values['model_settings'] = ModelSettingsExport.parse_obj(values)
        return values
