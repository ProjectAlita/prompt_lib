try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


class PromptVersionType(StrEnum):
    chat = 'chat'
    structured = 'structured'
    freeform = 'freeform'


class MessageRoles(StrEnum):
    system = 'system'
    user = 'user'
    assistant = 'assistant'


class CollectionPatchOperations(StrEnum):
    add = 'add'
    remove = 'remove'
