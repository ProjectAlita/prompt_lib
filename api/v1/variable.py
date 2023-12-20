from flask import request
from pydantic import ValidationError
from pylon.core.tools import log

from tools import api_tools, auth, config as c

from sqlalchemy.exc import IntegrityError


class ProjectAPI(api_tools.APIModeHandler):
    # @auth.decorators.check_api({
    #     "permissions": ["models.prompts.variable.create"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def post(self, project_id):
        try:
            # variable = self.module.create_variable(project_id, request.json)
            variable = VariableModel.validate(variable)
            with db.with_project_schema_session(project_id) as session:
                variable = Variable(**variable.dict())
                session.add(variable)
                session.commit()



            with db.with_project_schema_session(project_id) as session:
                for i in variables:
                    variable = Variable(**VariableModel.parse_obj(i).dict())
                    session.add(variable)
                session.commit()

            return variable.to_json(), 201
        except ValidationError as e:
            return e.errors(), 400
        except IntegrityError:
            return [{'loc': ['name'], 'msg': 'Variable already exists'}], 400

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompts.variable.update"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def put(self, project_id):
        try:
            variable = self.module.update_variable(project_id, request.json)
            return variable, 201
        except ValidationError as e:
            return e.errors(), 400
        except IntegrityError:
            return [{'loc': ['name'], 'msg': 'Variable already exists'}], 400

    # @auth.decorators.check_api({
    #     "permissions": ["models.prompts.variable.delete"],
    #     "recommended_roles": {
    #         c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
    #         c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
    #     }})
    def delete(self, project_id, variable_id):
        self.module.delete_variable(project_id, variable_id)
        return '', 204


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<string:mode>/<int:project_id>/<int:variable_id>',
        '<int:project_id>',
        '<int:project_id>/<int:variable_id>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
