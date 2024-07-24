from enum import Enum


class PromptEvents(str, Enum):
    prompt_change = 'prompt_change'
    prompt_version_change = 'prompt_version_change'
    prompt_deleted = 'prompt_deleted'
