from ....promptlib_shared.models.enums.all import PublishStatus, NotificationEventTypes
from sqlalchemy import desc
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.publish_utils import set_public_version_status
from pylon.core.tools import log
from tools import api_tools, auth, config as c
from pathlib import Path

from ...utils.utils import get_authors_data
from ....promptlib_shared.utils.utils import add_public_project_id


class PromptLibAPI(api_tools.APIModeHandler):

    @add_public_project_id
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.approve.get"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    @api_tools.endpoint_metrics
    def get(self, project_id: int, **kwargs):
        from ....usage.models.usage_api import UsageAPI
        file_path = Path(__file__)

        q = UsageAPI.query.with_entities(
            UsageAPI.user,
            UsageAPI.view_args,
            UsageAPI.date,
            UsageAPI.display_name,
        ).filter(
            UsageAPI.project_id == project_id,
            UsageAPI.mode == self.mode,
            UsageAPI.endpoint == f'api.{file_path.parent.name}.{self.mode}.{file_path.stem}',
            UsageAPI.method == 'POST',
            UsageAPI.status_code == 200
        ).order_by(desc(UsageAPI.date))
        audit_data = q.all()
        user_ids = [i[0] for i in audit_data]
        log.info(f'{user_ids=}')
        users: list = get_authors_data(author_ids=[i[0] for i in audit_data])
        log.info(f'{users=}')
        user_map = {i['id']: i for i in users}
        log.info(f'{user_map=}')
        result = []
        for i in audit_data:
            user, view_args, date, display_name = i
            struct = {
                'user': user_map.get(user),
                'version_id': view_args.get('version_id'),
                'date': date.isoformat(),
                'code_name': display_name
            }
            result.append(struct)


        return result, 200

    @add_public_project_id
    @auth.decorators.check_api({
        "permissions": ["models.prompt_lib.approve.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    @api_tools.endpoint_metrics
    def post(self, version_id: int, **kwargs):
        try:
            result = set_public_version_status(
                version_id, PublishStatus.published,
            )
        except Exception as e:
            log.error(e)
            return {"ok": False, "error": str(e)}, 400

        if not result['ok']:
            code = result.pop('error_code', 400)
            return result, code
        #
        prompt_version = result['result']
        return prompt_version, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '',
        '<int:version_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI
    }
