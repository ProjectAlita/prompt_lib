from pathlib import Path

from tools import db, rpc_tools

from ..models.all import PromptVersion


def change_prompt_icon(
        project_id: int,
        prompt_version_id: int,
        prompt_icon_path: Path,
        new_meta: dict,
) -> dict:
    with db.get_session(project_id) as session:
        version = session.query(PromptVersion).filter(
            PromptVersion.id == prompt_version_id
        ).first()
        if not version:
            return {'ok': False, 'msg': f'There is no such version id {prompt_version_id}'}

        icon_meta = version.meta.get('icon_meta', {}) if version.meta else {}

        if icon_meta:
            file_path: Path = prompt_icon_path.joinpath(
                icon_meta.get('name')
            )
            result = rpc_tools.RpcMixin().rpc.call.social_remove_image(
                file_path
            )
        else:
            result = {'data': {}, 'ok': True}
        if version.meta:
            version.meta['icon_meta'] = new_meta
        else:
            version.meta = {'icon_meta': new_meta}
        session.commit()
        return result
