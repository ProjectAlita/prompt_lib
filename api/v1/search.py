from flask import request
from pydantic import ValidationError
from pylon.core.tools import log
from sqlalchemy import or_, and_

from tools import api_tools, auth, config as c

from ...models.prompts import Prompt


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.prompts.search.post"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id):
        args = request.args
        search_query = "%{}%".format(args.get('query', ''))
        filter_ = and_(Prompt.version == 'latest',
                       or_(Prompt.name.like(search_query),
                           Prompt.description.like(search_query)))

        total, res = api_tools.get(
            project_id=project_id,
            args=args,
            data_model=Prompt,
            custom_filter=filter_,
            is_project_schema=True
            )

        return {
            "total": total,
            "rows": [prompt.to_json() | {'tags': [tag.to_json() for tag in prompt.tags]}
                     for prompt in res]
            }, 200

class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
