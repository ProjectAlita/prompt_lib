try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


class PromptVersionStatus(StrEnum):
    draft = 'draft'
    on_moderation = 'on_moderation'
    published = 'published'
    rejected = 'rejected'
    user_approval = 'user_approval'


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
