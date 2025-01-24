from typing import Optional, List, Dict

from pydantic.v1 import BaseModel, Extra


class MagicAssistantPredict(BaseModel):
    user_input: Optional[str]


class MagicAssistantResponse(BaseModel):
    name: str
    description: str
    context: str
    welcome_message: Optional[str]
    conversation_starters: Optional[List[str]]
    messages: Optional[List[dict]]

    class Config:
        extra = Extra.forbid

    @classmethod
    def create_from_dict(cls, data: Dict) -> "MagicAssistantResponse":
        new_data = {**cls.__annotations__, **data}
        for key in new_data:
            if key not in data:
                new_data[key] = None
        return cls.construct(**new_data)
