import re
from flask import g
from jinja2 import Environment, meta, DebugUndefined
from typing import Optional, List
from pylon.core.tools import web, log

from pydantic import parse_obj_as
from sqlalchemy.orm import joinedload, load_only, defer

from ..utils.ai_providers import AIProvider

from ..models.all import Prompt, PromptVersion
from ..models.pd.v1_structure import PromptV1Model
from traceback import format_exc
from tools import rpc_tools, db


class RPC:
    @web.rpc(f'prompt_lib_get_all', "get_all")
    def prompt_lib_get_all(self, project_id: int, with_versions: bool = False, **kwargs) -> list[dict]:
        # TODO: Support with_versions flag if we still need it
        with db.with_project_schema_session(project_id) as session:
            queryset = session.query(Prompt).order_by(Prompt.id.asc()).all()
            prompts = []
            for prompt in queryset:
                result = prompt.to_json()
                result['versions'] = []
                for v in prompt.versions:
                    v_data = v.to_json()
                    v_data['tags'] = []
                    for i in v.tags:
                        v_data['tags'].append(i.to_json())
                    result['versions'].append(v_data)
                prompts.append(result)

            results = parse_obj_as(List[PromptV1Model], prompts)
            return [prompt.dict() for prompt in results]

    @web.rpc("prompt_lib_get_by_id", "get_by_id")
    def prompts_get_by_id(self, project_id: int, prompt_id: int, version: str = 'latest', **kwargs) -> dict | None:
        with db.with_project_schema_session(project_id) as session:
            log.info(f'{prompt_id=}')
            log.info(f'{version=}')
            prompt_version = session.query(PromptVersion).options(
                joinedload(PromptVersion.prompt)
            ).options(
                joinedload(PromptVersion.variables)
            ).options(
                joinedload(PromptVersion.messages)
            ).filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.name == version
            ).one_or_none()
            if not prompt_version:
                return None

            result = prompt_version.to_json()
            if integration_uid := result.get('model_settings', {}).get('model', {}).get('integration_uid'):
                whole_settings = AIProvider.get_integration_settings(
                    project_id, integration_uid, prompt_version.model_settings
                )
                result['model_settings'] = whole_settings
                result['integration_uid'] = integration_uid if whole_settings else None

            messages = [example.to_json() for example in prompt_version.messages]
            examples = []
            for idx in range(0, len(messages), 2):
                if messages[idx]['role'] == 'user' and messages[idx + 1]['role'] == 'assistant':
                    examples.append({
                        "id": None,  # TODO: We have no example id anymore. Need to be fixed somehow.
                        "prompt_id": 1,
                        "input": messages[idx]['content'],
                        "output": messages[idx + 1]['content'],
                        "is_active": True,
                        "created_at": messages[idx + 1]['created_at']
                    })

            result['examples'] = examples
            result['variables'] = [var.to_json() for var in prompt_version.variables]
            result['tags'] = [tag.to_json() for tag in prompt_version.tags]
            result['versions'] = [{
                'id': version.id,
                'version': version.name,
                'tags': [tag.tag for tag in version.tags]
            } for version in prompt_version.prompt.versions]

            return result


#     @web.rpc("prompts_get_examples_by_prompt_id", "get_examples_by_prompt_id")
#     def prompts_get_examples_by_prompt_id(
#             self, project_id: int, prompt_id: int, **kwargs
#     ) -> list[dict]:
#         with db.with_project_schema_session(project_id) as session:
#             examples = session.query(Example).filter(Example.prompt_id == prompt_id).all()
#             return [example.to_json() for example in examples]

#     @web.rpc(f'prompts_create_example', "create_example")
#     def prompts_create_example(self, project_id: int, example: dict, from_test_input: bool = False, **kwargs) -> dict:
#         example = ExampleModel.validate(example)
#         with db.with_project_schema_session(project_id) as session:
#             example = Example(**example.dict())
#             session.add(example)
#             if from_test_input:
#                 session.query(Prompt).filter(Prompt.id == example.prompt_id).update(
#                     {'test_input': None}
#                 )
#             session.commit()
#             return example.to_json()

#     @web.rpc(f'prompts_create_examples_bulk', "create_examples_bulk")
#     def prompts_create_examples_bulk(self, project_id: int, examples: List[dict], **kwargs) -> None:
#         examples = parse_obj_as(List[ExampleModel], examples)
#         with db.with_project_schema_session(project_id) as session:
#             for i in examples:
#                 example = Example(**i.dict())
#                 session.add(example)
#             session.commit()

#     @web.rpc(f'prompts_update_example', "update_example")
#     def prompts_update_example(self, project_id: int, example: dict, **kwargs) -> bool:
#         example = ExampleUpdateModel.validate(example)
#         with db.with_project_schema_session(project_id) as session:
#             session.query(Example).filter(Example.id == example.id).update(
#                 example.dict(exclude={'id'}, exclude_none=True)
#             )
#             session.commit()
#             updated_example = session.query(Example).get(example.id)
#             return updated_example.to_json()

#     @web.rpc(f'prompts_delete_example', "delete_example")
#     def prompts_delete_example(self, project_id: int, example_id: int, **kwargs) -> bool:
#         with db.with_project_schema_session(project_id) as session:
#             example = session.query(Example).get(example_id)
#             if example:
#                 session.delete(example)
#                 session.commit()
#             return True

#     @web.rpc("prompts_get_versions_by_prompt_name", "get_versions_by_prompt_name")
#     def prompts_get_versions_by_prompt_name(self, project_id: int, prompt_name: str) -> list[dict]:
#         with db.with_project_schema_session(project_id) as session:
#             prompts = session.query(Prompt).filter(
#                 Prompt.name == prompt_name
#             ).order_by(
#                 Prompt.version
#             ).all()
#             return [prompt.to_json() for prompt in prompts]

#     @web.rpc("prompts_get_ai_provider", "get_ai_provider")
#     def prompts_get_ai_provider(self) -> AIProvider:
#         return AIProvider

#     @web.rpc(f'prompts_prepare_prompt_struct', "prepare_prompt_struct")
#     def prompts_prepare_prompt_struct(self, project_id: int, prompt_id: Optional[int],
#                                       input_: str = '', context: str = '', examples: list = [],
#                                       variables: dict = {}, ignore_template_error: bool = False,
#                                       chat_history: Optional[dict] = None, addons: Optional[dict] = None,
#                                       **kwargs) -> dict:

#         # example_template = '\ninput: {input}\noutput: {output}'

#         prompt_struct = {
#             "context": context,
#             "examples": examples,  # list of dicts {"input": "value", "output": "value"}
#             "variables": variables,  # list of dicts {"var_name": "value"}
#             "prompt": input_
#         }
#         if chat_history:
#             prompt_struct['chat_history'] = chat_history
#         if addons:
#             prompt_struct['addons'] = addons
#         if prompt_id:
#             prompt_template = self.get_by_id(project_id, prompt_id)
#             if not prompt_template:
#                 raise Exception(f"Prompt with id {prompt_id} in project {project_id} not found")
#             prompt_struct['context'] = prompt_template['prompt'] + prompt_struct['context']
#             for example in prompt_template['examples']:
#                 if not example['is_active']:
#                     continue
#                 prompt_struct['examples'].append({
#                     "input": example['input'],
#                     "output": example['output']
#                 })
#             for variable in prompt_template['variables']:
#                 if not prompt_struct['variables'].get(variable['name']):
#                     prompt_struct['variables'][variable['name']] = variable['value']
#             # if prompt_struct['prompt']:
#             #     prompt_struct['variables']['prompt'] = prompt_struct['prompt']

#         prompt_struct = resolve_variables(prompt_struct, ignore_template_error=ignore_template_error)
#         prompt_struct.pop('variables')

#         # for example in prompt_struct['examples']:
#         #     prompt_struct['context'] += example_template.format(**example)

#         # if prompt_struct['prompt']:
#         #     prompt_struct['context'] += example_template.format(input=prompt_struct['prompt'], output='')

#         # if prompt_struct['prompt']:
#         #     prompt_struct['prompt'] = example_template.format(input=prompt_struct['prompt'], output='')
#         log.info(f"FINAL: {prompt_struct=}")
#         return prompt_struct


# def resolve_variables(prompt_struct: dict, ignore_template_error: bool = False) -> dict:
#     try:
#         environment = Environment(undefined=DebugUndefined)
#         ast_c = environment.parse(prompt_struct['context'])
#         ast_p = environment.parse(prompt_struct['prompt'])
#         if len(set(meta.find_undeclared_variables(ast_p))) > 0:
#             template_p = environment.from_string(prompt_struct['prompt'])
#             prompt_struct['prompt'] = template_p.render(**prompt_struct['variables'])

#         if 'prompt' in set(meta.find_undeclared_variables(ast_c)):
#             prompt_struct['variables']['prompt'] = prompt_struct['prompt']
#             prompt_struct['prompt'] = ''

#         template = environment.from_string(prompt_struct['context'])
#         prompt_struct['context'] = template.render(**prompt_struct['variables'])

#     except:
#         log.critical(format_exc())
#         if not ignore_template_error:
#             raise Exception("Invalid jinja template in context")

#     return prompt_struct
