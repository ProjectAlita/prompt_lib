import re
from jinja2 import Environment, meta, DebugUndefined
from typing import Optional, List
from pylon.core.tools import web, log

from pydantic import parse_obj_as
from sqlalchemy.orm import joinedload, load_only, defer
from ..models.example import Example
from ..models.pd.example import ExampleModel, ExampleUpdateModel
from ..models.prompts import Prompt
from ..models.pd.prompts_pd import PromptModel, PromptUpdateModel, PromptUpdateNameModel
from ..models.variable import Variable
from ..utils.ai_providers import AIProvider
from traceback import format_exc
from tools import rpc_tools, db


class RPC:

    @web.rpc(f'prompts_predict', "predict")
    def prompts_predict(self, project_id, integration, model_settings, text_prompt, **kwargs) -> list[dict]:
        rpc = rpc_tools.RpcMixin().rpc.call
        rpc_name = integration.name + "__predict"
        rpc_func = getattr(rpc, rpc_name)
        if integration.name == 'ai_dial':
            result = rpc_func(project_id, model_settings, text_prompt, **kwargs)
        else:
            result = rpc_func(project_id, model_settings, text_prompt)
        return result

    @web.rpc(f'prompts_get_all', "get_all")
    def prompts_get_all(self, project_id: int, with_versions: bool = False, **kwargs) -> list[dict]:
        with db.with_project_schema_session(project_id) as session:
            queryset = session.query(Prompt).order_by(Prompt.id.asc()).all()
            if with_versions:
                return [prompt.to_json() | {'tags': [tag.to_json() for tag in prompt.tags]}
                        for prompt in queryset]
            prompts = [prompt.to_json() | {'tags': [tag.to_json() for tag in prompt.tags]}
                       for prompt in queryset if prompt.version == 'latest']
            for prompt in prompts:
                prompt['versions'] = [{
                    'id': version.id,
                    'version': version.version,
                    'tags': [tag.tag for tag in version.tags]
                } for version in queryset if version.name == prompt['name']]
            return prompts

    @web.rpc("prompts_get_by_id", "get_by_id")
    def prompts_get_by_id(self, project_id: int, prompt_id: int, version: str = '', **kwargs) -> dict | None:
        if version:
            version_id = self.get_version_id(project_id, prompt_id, version)
            if not version_id:
                return None
            prompt_id = version_id

        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).options(
                joinedload(Prompt.examples)
            ).options(
                joinedload(Prompt.variables)
            ).filter(
                Prompt.id == prompt_id,
            ).one_or_none()
            if not prompt:
                return None

            result = prompt.to_json(exclude_fields=set(['integration_id', ]))
            if prompt.integration_uid:
                whole_settings = AIProvider.get_integration_settings(
                    project_id, prompt.integration_uid, prompt.model_settings
                )
                result['model_settings'] = whole_settings
                result['integration_uid'] = prompt.integration_uid if whole_settings else None
            result['examples'] = [example.to_json() for example in prompt.examples]
            result['variables'] = [var.to_json() for var in prompt.variables]
            result['tags'] = [tag.to_json() for tag in prompt.tags]

            versions = session.query(Prompt).options(
                defer(Prompt.prompt), defer(Prompt.test_input), defer(Prompt.model_settings)
            ).filter(Prompt.name == prompt.name).all()
            result['versions'] = [{
                'id': version.id,
                'version': version.version,
                'tags': [tag.tag for tag in version.tags]
            } for version in versions]

            return result

    @web.rpc("prompts_get_version_id", "get_version_id")
    def prompts_get_version_id(self, project_id: int, prompt_id: int, version: str) -> dict | None:
        with db.with_project_schema_session(project_id) as session:
            if subquery := session.query(Prompt.name).filter(
                    Prompt.id == prompt_id
            ).one_or_none():
                if ids := session.query(Prompt.id).filter(
                        Prompt.name.in_(subquery),
                        Prompt.version == version,
                ).one_or_none():
                    return ids[0]

    @web.rpc(f'prompts_create', "create")
    def prompts_create(self, project_id: int, prompt: dict, **kwargs) -> dict:
        prompt['project_id'] = project_id
        prompt = PromptModel.validate(prompt)
        with db.with_project_schema_session(project_id) as session:
            prompt = Prompt(**prompt.dict(exclude={'project_id'}))
            session.add(prompt)
            session.commit()
            return prompt.to_json()

    @web.rpc(f'prompts_update', "update")
    def prompts_update(self, project_id: int, prompt: dict, **kwargs) -> bool:
        prompt['project_id'] = project_id
        embedding_id = int(prompt["embedding"])
        top_k = prompt.get("embedding_settings", {}).get("top_k", 20)
        cutoff = prompt.get("embedding_settings", {}).get("cutoff", 0.1)
        if not embedding_id:
            with db.with_project_schema_session(project_id) as session:
                _prompt = session.query(Prompt).get(prompt["id"])
                _prompt.embeddings = {}
                session.commit()
        else:
            with db.with_project_schema_session(project_id) as session:
                if "embeddings" in self.context.module_manager.modules:
                    embedding = rpc_tools.RpcMixin().rpc.call.embeddings_get_by_id(project_id, embedding_id).to_json()
                    embedding["top_k"] = top_k
                    embedding["cutoff"] = cutoff
                    _prompt = session.query(Prompt).get(prompt["id"])
                    _prompt.embeddings = embedding
                    session.commit()
        prompt = PromptUpdateModel.validate(prompt)
        with db.with_project_schema_session(project_id) as session:
            session.query(Prompt).filter(Prompt.id == prompt.id).update(
                prompt.dict(exclude={'id', 'project_id'}, exclude_none=True)
            )
            session.commit()
            updated_prompt = session.query(Prompt).get(prompt.id)
            return updated_prompt.to_json()

    @web.rpc(f'prompts_update_name', "update_name")
    def prompts_update_name(self, project_id: int, prompt_id: int, prompt_date: dict) -> bool:
        prompt_data = PromptUpdateNameModel.validate(prompt_date)
        with db.with_project_schema_session(project_id) as session:
            if subquery := session.query(Prompt.name).filter(
                    Prompt.id == prompt_id
            ).one_or_none():
                session.query(Prompt).filter(
                    Prompt.name.in_(subquery)
                ).update(prompt_data.dict())
                session.commit()
            return True

    @web.rpc(f'prompts_delete', "delete")
    def prompts_delete(self, project_id: int, prompt_id: int, **kwargs) -> bool:
        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).get(prompt_id)
            examples = session.query(Example).filter(Example.prompt_id == prompt_id).all()
            if prompt and prompt.version == 'latest':
                versions = session.query(Prompt).filter(Prompt.name == prompt.name).all()
                for version in versions:
                    session.delete(version)
            if prompt:
                session.delete(prompt)
            for example in examples:
                session.delete(example)

            session.commit()
            return True

    @web.rpc("prompts_get_examples_by_prompt_id", "get_examples_by_prompt_id")
    def prompts_get_examples_by_prompt_id(
            self, project_id: int, prompt_id: int, **kwargs
    ) -> list[dict]:
        with db.with_project_schema_session(project_id) as session:
            examples = session.query(Example).filter(Example.prompt_id == prompt_id).all()
            return [example.to_json() for example in examples]

    @web.rpc(f'prompts_create_example', "create_example")
    def prompts_create_example(self, project_id: int, example: dict, from_test_input: bool = False, **kwargs) -> dict:
        example = ExampleModel.validate(example)
        with db.with_project_schema_session(project_id) as session:
            example = Example(**example.dict())
            session.add(example)
            if from_test_input:
                session.query(Prompt).filter(Prompt.id == example.prompt_id).update(
                    {'test_input': None}
                )
            session.commit()
            return example.to_json()

    @web.rpc(f'prompts_create_examples_bulk', "create_examples_bulk")
    def prompts_create_examples_bulk(self, project_id: int, examples: List[dict], **kwargs) -> None:
        examples = parse_obj_as(List[ExampleModel], examples)
        with db.with_project_schema_session(project_id) as session:
            for i in examples:
                example = Example(**i.dict())
                session.add(example)
            session.commit()

    @web.rpc(f'prompts_update_example', "update_example")
    def prompts_update_example(self, project_id: int, example: dict, **kwargs) -> bool:
        example = ExampleUpdateModel.validate(example)
        with db.with_project_schema_session(project_id) as session:
            session.query(Example).filter(Example.id == example.id).update(
                example.dict(exclude={'id'}, exclude_none=True)
            )
            session.commit()
            updated_example = session.query(Example).get(example.id)
            return updated_example.to_json()

    @web.rpc(f'prompts_delete_example', "delete_example")
    def prompts_delete_example(self, project_id: int, example_id: int, **kwargs) -> bool:
        with db.with_project_schema_session(project_id) as session:
            example = session.query(Example).get(example_id)
            if example:
                session.delete(example)
                session.commit()
            return True

    @web.rpc("prompts_get_versions_by_prompt_name", "get_versions_by_prompt_name")
    def prompts_get_versions_by_prompt_name(self, project_id: int, prompt_name: str) -> list[dict]:
        with db.with_project_schema_session(project_id) as session:
            prompts = session.query(Prompt).filter(
                Prompt.name == prompt_name
            ).order_by(
                Prompt.version
            ).all()
            return [prompt.to_json() for prompt in prompts]

    @web.rpc("prompts_get_ai_provider", "get_ai_provider")
    def prompts_get_ai_provider(self) -> AIProvider:
        return AIProvider

    @web.rpc(f'prompts_prepare_prompt_struct', "prepare_prompt_struct")
    def prompts_prepare_prompt_struct(self, project_id: int, prompt_id: Optional[int],
                                      input_: str = '', context: str = '', examples: list = [],
                                      variables: dict = {}, ignore_template_error: bool = False,
                                      chat_history: Optional[dict] = None, addons: Optional[dict] = None,
                                      **kwargs) -> dict:

        # example_template = '\ninput: {input}\noutput: {output}'

        prompt_struct = {
            "context": context,
            "examples": examples,  # list of dicts {"input": "value", "output": "value"}
            "variables": variables,  # list of dicts {"var_name": "value"}
            "prompt": input_
        }
        if chat_history:
            prompt_struct['chat_history'] = chat_history
        if addons:
            prompt_struct['addons'] = addons
        if prompt_id:
            prompt_template = self.get_by_id(project_id, prompt_id)
            if not prompt_template:
                raise Exception(f"Prompt with id {prompt_id} in project {project_id} not found")
            prompt_struct['context'] = prompt_template['prompt'] + prompt_struct['context']
            for example in prompt_template['examples']:
                if not example['is_active']:
                    continue
                prompt_struct['examples'].append({
                    "input": example['input'],
                    "output": example['output']
                })
            for variable in prompt_template['variables']:
                if not prompt_struct['variables'].get(variable['name']):
                    prompt_struct['variables'][variable['name']] = variable['value']
            # if prompt_struct['prompt']:
            #     prompt_struct['variables']['prompt'] = prompt_struct['prompt']

        prompt_struct = resolve_variables(prompt_struct, ignore_template_error=ignore_template_error)
        prompt_struct.pop('variables')

        # for example in prompt_struct['examples']:
        #     prompt_struct['context'] += example_template.format(**example)

        # if prompt_struct['prompt']:
        #     prompt_struct['context'] += example_template.format(input=prompt_struct['prompt'], output='')

        # if prompt_struct['prompt']:
        #     prompt_struct['prompt'] = example_template.format(input=prompt_struct['prompt'], output='')
        log.info(f"FINAL: {prompt_struct=}")
        return prompt_struct


def resolve_variables(prompt_struct: dict, ignore_template_error: bool = False) -> dict:
    try:
        environment = Environment(undefined=DebugUndefined)
        ast_c = environment.parse(prompt_struct['context'])
        ast_p = environment.parse(prompt_struct['prompt'])
        if len(set(meta.find_undeclared_variables(ast_p))) > 0:
            template_p = environment.from_string(prompt_struct['prompt'])
            prompt_struct['prompt'] = template_p.render(**prompt_struct['variables'])

        if 'prompt' in set(meta.find_undeclared_variables(ast_c)):
            prompt_struct['variables']['prompt'] = prompt_struct['prompt']
            prompt_struct['prompt'] = ''

        template = environment.from_string(prompt_struct['context'])
        prompt_struct['context'] = template.render(**prompt_struct['variables'])

    except:
        log.critical(format_exc())
        if not ignore_template_error:
            raise Exception("Invalid jinja template in context")

    return prompt_struct
