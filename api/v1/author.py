from queue import Empty

from pylon.core.tools import log

from tools import api_tools, auth, config as c, rpc_tools

from ...utils.utils import get_author_data
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.author import get_stats
from ....promptlib_shared.utils.utils import add_public_project_id


class PromptLibAPI(api_tools.APIModeHandler):
    @add_public_project_id
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.author.detail"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
            },
        }
    )
    @api_tools.endpoint_metrics
    def get(self, author_id: int, *, project_id: int):
        author: dict = get_author_data(author_id=author_id)
        if not author:
            return {'error': f'author with id {author_id} not found'}
        try:
            author_project_id = self.module.context.rpc_manager.timeout(2).projects_get_personal_project_id(
                author['id'])
            stats = get_stats(author_project_id, author['id'])
            author.update(stats)

            rpc_timeout = rpc_tools.RpcMixin().rpc.timeout
            res = {'total_datasources': 0, 'public_datasources': 0}
            try:
                res = rpc_timeout(5).datasources_get_stats(author_project_id, author_id)
            except Empty:
                log.warning("datasources plugin is not available, related stats will be empty")
            finally:
                author.update(res)

            res = {'total_applications': 0, 'public_applications': 0}
            try:
                res = rpc_timeout(5).applications_get_stats(author_project_id, author_id)
            except Empty:
                log.warning("applications plugin is not available, related stats will be empty")
            finally:
                author.update(res)

            res = {'total_conversations': 0, 'public_conversations': 0}
            try:
                res = rpc_timeout(5).chat_get_stats(author_project_id, author_id)
            except Empty:
                log.warning("chat plugin is not available, related stats will be empty")
            finally:
                author.update(res)

        except Empty:
            ...
        return author, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        # '<int:project_id>/<int:author_id>',
        '<int:author_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
