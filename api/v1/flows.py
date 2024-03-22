from collections import defaultdict

from pylon.core.tools import log

from tools import api_tools, db, config as c, auth

from ....prompt_lib.models.all import Prompt


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": [
            "models.flows.flows.list",
            "models.flows.flow.details",
            "models.flows.flows.create",
        ],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id: int, **kwargs):
        with db.with_project_schema_session(project_id) as session:
            query = session.query(Prompt).with_entities(Prompt.id, Prompt.name, Prompt.version)
            result = defaultdict(list)
            for id_, name, version in query.all():
                result[name].append({'id': id_, 'version': version})
            for i in result:
                result[i].sort(key=lambda x: x['id'])
            return result, 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
