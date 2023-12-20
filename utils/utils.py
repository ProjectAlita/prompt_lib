from queue import Empty
from functools import wraps
from typing import Set, Callable

from tools import VaultClient, auth, rpc_tools
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


def add_public_project_id(f: Callable) -> Callable:
    wraps(f)
    def wrapper(*args, **kwargs):
        secrets = VaultClient().get_all_secrets()
        try:
            public_project_id = secrets['ai_project_id']
        except KeyError:
            return {'error': "'ai_project_id' not set"}, 400
        kwargs.update({'project_id': public_project_id})
        return f(*args, **kwargs)
    return wrapper


def get_author_data(author_id: int) -> dict:
    try:
        author_data = auth.get_user(user_id=author_id)
    except RuntimeError:
        return {}
    try:
        user_data = rpc_tools.RpcMixin().rpc.timeout(2).social_get_user(author_data['id'])
        avatar = user_data['avatar']
    except (Empty, KeyError):
        avatar = None
    author_data['avatar'] = avatar
    return author_data
