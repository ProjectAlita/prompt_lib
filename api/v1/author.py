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
    def get(self, project_id: int, author_id: int):
        author: AuthorDetailModel = get_author_data(author_id=author_id)
        stats = get_stats(project_id, author_id)
        for key, value in stats.items():
             setattr(author, key, value)
        return author.dict(), 200

class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        # '<int:project_id>/<int:author_id>',
        '<int:author_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
