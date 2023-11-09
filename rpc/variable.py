from typing import List
from pylon.core.tools import web, log

from tools import db

from ..models.pd.variable import VariableModel, VariableUpdateModel
from ..models.variable import Variable


class RPC:
    @web.rpc("prompts_get_variable_by_prompt_id", "get_variables_by_prompt_id")
    def prompts_get_variable_by_prompt_id(
            self, project_id: int, prompt_id: int, **kwargs
    ) -> List[dict]:
        with db.with_project_schema_session(project_id) as session:
            variables = session.query(Variable).filter(Variable.prompt_id == prompt_id).all()
            return [variable.to_json() for variable in variables]

    # @web.rpc(f'prompts_create_variable', "create_variable")
    # def prompts_create_variable(self, project_id: int, variable: dict, **kwargs) -> dict:
    #     variable = VariableModel.validate(variable)
    #     with db.with_project_schema_session(project_id) as session:
    #         variable = Variable(**variable.dict())
    #         session.add(variable)
    #         session.commit()
    #         return variable.to_json()

    # @web.rpc('prompts_create_variables_bulk', 'create_variables_bulk')
    # def create_variables_bulk(self, project_id: int, variables: List[dict], **kwargs) -> None:
    #     with db.with_project_schema_session(project_id) as session:
    #         for i in variables:
    #             variable = Variable(**VariableModel.parse_obj(i).dict())
    #             session.add(variable)
    #         session.commit()

    @web.rpc(f'prompts_update_variable', "update_variable")
    def prompts_update_variable(self, project_id: int, variable: dict, **kwargs) -> bool:
        variable = VariableUpdateModel.validate(variable)
        with db.with_project_schema_session(project_id) as session:
            session.query(Variable).filter(Variable.id == variable.id).update(
                variable.dict(exclude={'id'}, exclude_none=True)
            )
            session.commit()
            updated_variable = session.query(Variable).get(variable.id)
            return updated_variable.to_json()

    @web.rpc(f'prompts_delete_variable', "delete_variable")
    def prompts_delete_variable(self, project_id: int, variable_id: int, **kwargs) -> None:
        with db.with_project_schema_session(project_id) as session:
            variable = session.query(Variable).get(variable_id)
            if variable:
                session.delete(variable)
                session.commit()
