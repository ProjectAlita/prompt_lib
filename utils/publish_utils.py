from tools import db, VaultClient, auth, rpc_tools
from pylon.core.tools import log


def is_public_project(project_id: int = None):
    ai_project_id = get_public_project_id()
    return ai_project_id == project_id, int(ai_project_id)


def get_public_project_id():
    secrets = VaultClient().get_all_secrets()
    project_id = secrets.get("ai_project_id")
    if not project_id:
        raise Exception("Public project is not set")
    return int(project_id)
