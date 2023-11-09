try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


class PromptVersionStatus(StrEnum):
    draft = 'draft'
    on_moderation = 'on_moderation'


class PromptVersionType(StrEnum):
    chat = 'chat'
    structured = 'structured'
    freeform = 'freeform'


class MessageRoles(StrEnum):
    system = 'system'
    human = 'human'
    bot = 'bot'
