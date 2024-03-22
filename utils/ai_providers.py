from typing import Optional

from tools import rpc_tools
from pylon.core.tools import log


class IntegrationNotFound(Exception):
    "Raised when integration is not found"


class AIProvider:
    rpc = rpc_tools.RpcMixin().rpc.call

    @classmethod
    def get_integration_settings(
            cls, project_id: int, integration_uid: str, prompt_settings: dict
    ) -> Optional[dict]:
        if not prompt_settings:
            prompt_settings = {}
        try:
            integration = cls.get_integration(project_id, integration_uid)
        except IntegrationNotFound as e:
            log.error(str(e))
            return None
        return {**integration.settings, **prompt_settings}

    @classmethod
    def get_integration(cls, project_id: int, integration_uid: str):
        integration = cls.rpc.integrations_get_by_uid(
            integration_uid=integration_uid,
            project_id=project_id,
            check_all_projects=True
        )
        if integration is None:
            raise IntegrationNotFound(
                f"Integration is not found when project_id={project_id}, integration_uid={integration_uid}"
            )
        return integration

    @classmethod
    def _get_rpc_function(cls, integration_name, suffix="__predict"):
        rpc_name = integration_name + suffix
        rpc_func = getattr(cls.rpc, rpc_name)
        return rpc_func

    @classmethod
    def predict(cls, project_id: int, integration, request_settings: dict, prompt_struct: dict | list, **kwargs):
        rpc_func = cls._get_rpc_function(integration.name)
        settings = {**integration.settings, **request_settings}
        if integration.name == 'ai_dial':
            result = rpc_func(project_id, settings, prompt_struct,
                              **kwargs)  # TODO: remove when we add kwargs to all rpc functions
        else:
            if isinstance(prompt_struct, list):
                # So, our integrations (except ai_dial) ...
                # ... always try to construct their own message list
                # Need to give them legacy prompt structure for now
                prompt_struct = cls._make_legacy_prompt_struct(prompt_struct)
            result = rpc_func(project_id, settings, prompt_struct)
        return result

    @staticmethod
    def _make_legacy_prompt_struct(list_prompt_struct):
        # Step A: make conversation
        conversation = {
            "context": [],
            "examples": [],
            "chat_history": [],
            "input": []
        }
        #
        for idx, message in enumerate(list_prompt_struct):
            if message["role"] == "system" and not message.get("name"):
                conversation["context"].append(message)
            if message.get("name") in ("example_user", "example_assistant"):
                conversation["examples"].append(message)
            if message["role"] == "user" and idx != len(list_prompt_struct) - 1:
                conversation["chat_history"].append(message)
            if message["role"] == "assistant":
                conversation["chat_history"].append(message)
        #
        if list_prompt_struct[-1]["role"] == "user":
            conversation["input"].append(list_prompt_struct[-1])
        # Step B: make legacy prompt struct
        # - context
        context = "\n".join([
            item["content"] for item in conversation["context"]
        ])
        # - examples
        examples = []
        example = None
        #
        for item in conversation["examples"]:
            if example is None:
                example = {}
            #
            if item["name"] == "example_user":
                example["input"] = item["content"]
            else:
                example["output"] = item["content"]
            #
            if "input" in example and "output" in example:
                examples.append(example)
                example = None
        #
        if example is not None:
            examples.append(example)
        # - chat_history
        chat_history = []
        #
        for item in conversation["chat_history"]:
            chat_history.append(item)  # Should work as-is
        # - prompt
        prompt = "\n".join([
            item["content"] for item in conversation["input"]
        ])
        # - result
        return {
            "context": context,
            "examples": examples,
            "chat_history": chat_history,
            "prompt": prompt,
        }

    @classmethod
    def parse_settings(cls, integration, settings):
        rpc_func = cls._get_rpc_function(integration.name, "__parse_settings")
        return rpc_func(settings)

    @classmethod
    def chat_completion(cls, project_id, integration, request_data):
        rpc_func = cls._get_rpc_function(integration.name, "__chat_completion")
        return rpc_func(project_id, integration.settings, request_data)

    @classmethod
    def completion(cls, project_id, integration, request_data):
        rpc_func = cls._get_rpc_function(integration.name, "__completion")
        return rpc_func(project_id, integration.settings, request_data)
