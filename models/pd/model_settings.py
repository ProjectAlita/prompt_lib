from typing import Optional

from pydantic.v1 import Field, BaseModel, confloat, conint, PositiveInt
from ....promptlib_shared.models.pd.chat import IntegrationDataMixin


class ModelInfoDetailModel(BaseModel):
    integration_name: Optional[str] = None
    integration_uid: Optional[str] = None
    model_name: Optional[str] = Field(alias='name', default=None)

    class Config:
        allow_population_by_field_name = True


class ModelInfoCreateModel(IntegrationDataMixin):
    integration_name: Optional[str] = None
    model_name: Optional[str] = Field(alias='name', default=None)

    class Config:
        allow_population_by_field_name = True


class ModelSettingsBaseModel(BaseModel):
    temperature: Optional[confloat(ge=0, le=2)] = None
    top_k: Optional[conint(ge=1, le=40)] = None
    top_p: Optional[confloat(ge=0, le=1)] = None
    max_tokens: Optional[PositiveInt] = None
    stream: bool = False
    model: Optional[ModelInfoDetailModel] = Field(default_factory=ModelInfoDetailModel)
    suggested_models: Optional[list] = []

    @property
    def merged(self) -> dict:
        model_settings = self.dict()
        if hasattr(self.model, 'dict'):
            model_settings.update(self.model.dict())
        elif isinstance(self.model, dict):
            model_settings.update(self.model)
        if "model_name" not in model_settings and "name" in model_settings:
            model_settings["model_name"] = model_settings["name"]
        return model_settings


class ModelSettingsCreateModel(ModelSettingsBaseModel):
    model: Optional[ModelInfoCreateModel] = {}
