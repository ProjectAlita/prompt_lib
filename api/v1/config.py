from flask import g
from pylon.core.tools import log

from tools import api_tools, auth, config as c

from ...models.pd.legacy.config_pd import ModelsConfig, TokenPD


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.config"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": True},
        }})
    def get(self, project_id: int, **kwargs):
        data: ModelsConfig = self.module.get_config(project_id=project_id, user_id=g.auth.id)

        table_data = [
            {'key': k, 'value': v, 'weight': 4}
            for k, v in data.dict(exclude={'integrations', 'token'}).items()
        ]

        token_data = {'key': 'token', 'value': {'token': None, 'expires': None}, 'weight': 6}
        if data.token:
            token_data['value']['token'] = data.token.encoded
            try:
                token_data['value']['expires'] = data.token.expires.isoformat(timespec='seconds')
            except AttributeError:
                token_data['value']['expires'] = None
        table_data.append(token_data)

        integrations_data = {
            'key': 'integration_uid',
            'value': data.selected_integration.get('uid'),
            'action': data.formatted_integrations,
            'weight': 2
        }
        table_data.append(integrations_data)

        return table_data, 200

    @auth.decorators.check_api({
        "permissions": ["models.config"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def put(self, project_id: int, **kwargs):
        # used to regenerate token from ui
        token: TokenPD = self.module.regenerate_token(user_id=g.auth.id)
        return {'token': {'token': token.encoded, 'expires': token.expires.isoformat(timespec='seconds')}}, 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
