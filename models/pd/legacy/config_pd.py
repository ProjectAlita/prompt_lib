from datetime import datetime
from itertools import groupby
from typing import Optional

from pydantic import BaseModel


class TokenPD(BaseModel):
    id: int
    uuid: Optional[str]
    expires: Optional[datetime]
    user_id: int
    name: str

    @property
    def encoded(self) -> str:
        from tools import auth
        return auth.encode_token(self.id)


class ModelsConfig(BaseModel):
    token: Optional[TokenPD] = None
    project_id: int
    integrations: list = []
    url: str

    @property
    def formatted_integrations(self) -> dict:
        return {
            str(k): list(v)
            for k, v in
            groupby(sorted(self.integrations, key=lambda x: x['name']), lambda x: x['name'])
        }

    @property
    def selected_integration(self) -> dict:
        try:
            return next(i for i in self.integrations if i['is_default'])
        except StopIteration:
            try:
                return self.integrations[0]
            except IndexError:
                return {}
