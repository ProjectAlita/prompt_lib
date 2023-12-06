import functools
from typing import Set, Callable

from tools import VaultClient
from ..models.enums.all import PromptVersionStatus


def determine_prompt_status(version_statuses: Set[PromptVersionStatus]) -> PromptVersionStatus:
    status_priority = (
        PromptVersionStatus.rejected,
        PromptVersionStatus.on_moderation,
        PromptVersionStatus.published,
        PromptVersionStatus.draft,
        # PromptVersionStatus.user_approval,
    )

    for status in status_priority:
        if status in version_statuses:
            return status


def add_publuc_project_id(f: Callable) -> Callable:
    functools.wraps(f)
    def wrapper(*args, **kwargs):
        secrets = VaultClient().get_all_secrets()
        kwargs.update({'project_id': secrets.get("ai_project_id")})
        return f(*args, **kwargs)
    return wrapper
