from queue import Empty

from pylon.core.tools import log

from tools import api_tools, auth, config as c

from ...utils.utils import get_author_data, add_public_project_id
from ...utils.constants import PROMPT_LIB_MODE
from ...models.pd.authors import AuthorDetailModel
from ...utils.author import get_stats


class PromptLibAPI(api_tools.APIModeHandler):
    @add_public_project_id
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.author.detail"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def get(self, author_id: int, *, project_id: int):
        author: AuthorDetailModel = get_author_data(author_id=author_id)
        try:
            author_project_id = self.module.context.rpc_manager.timeout(2).projects_get_personal_project_id(author.id)
            stats = get_stats(author_project_id, author.id)
            for key, value in stats.items():
                 setattr(author, key, value)
        except Empty:
            ...
        return author.dict(), 200

class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        # '<int:project_id>/<int:author_id>',
        '<int:author_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
