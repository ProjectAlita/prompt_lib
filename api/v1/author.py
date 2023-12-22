from typing import List
from flask import jsonify
from pylon.core.tools import log

from tools import api_tools, auth, config as c

from ...utils.utils import get_author_data
from ...utils.constants import PROMPT_LIB_MODE
from ...models.all import Prompt, PromptVersion
from ...models.pd.authors import AuthorDetailModel
from ...models.enums.all import PromptVersionStatus
from ...utils.prompt_utils import list_prompts


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.author.detail"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    def get(self, project_id: int, author_id: int):
        author: AuthorDetailModel = get_author_data(author_id=author_id)

        public_prompts, _ = list_prompts(
            project_id=project_id,
            filters=[
                Prompt.versions.any(PromptVersion.status == PromptVersionStatus.published),
                Prompt.versions.any(PromptVersion.author_id == author_id)
            ],
            limit=None,
            with_likes=False
        )
        author.public_prompts = public_prompts

        return author.dict(), 200

class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:author_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
