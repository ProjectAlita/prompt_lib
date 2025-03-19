from pathlib import Path

from pylon.core.tools import module, log

from tools import db, theme, VaultClient


class Module(module.ModuleModel):
    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

        config = self.descriptor.config
        base_path = Path(__file__).parent.joinpath("data")

        self.prompt_icon_path = Path(
            config.get("prompt_icon_path", base_path.joinpath("prompt_icon"))
        )

    def init(self):
        log.info("Initializing")
        #
        self.descriptor.init_all()
        # self.init_db()
        #
        try:
            theme.register_section(
                "models",
                "Models",
                kind="holder",
                location="left",
                permissions={
                    "permissions": ["models"],
                    "recommended_roles": {
                        "administration": {"admin": True, "editor": True, "viewer": True},
                        "default": {"admin": True, "editor": True, "viewer": True},
                    }
                }
            )
        except (ValueError, RuntimeError):
            ...

        theme.register_subsection(
            "models", "prompts",
            "Prompts",
            title="AI Prompts",
            kind="slot",
            prefix="prompts_",
            weight=5,
            permissions={
                "permissions": ["models.prompts"],
                "recommended_roles": {
                    "administration": {"admin": True, "editor": True, "viewer": True},
                    "default": {"admin": True, "editor": True, "viewer": True},
                }
            }
        )

        theme.register_subsection(
            "models", "config",
            "Config",
            title="Config",
            kind="slot",
            prefix="models_config_",
            # weight=5,
            permissions={
                "permissions": ["models.config"],
                "recommended_roles": {
                    "administration": {"admin": True, "editor": False, "viewer": False},
                    "default": {"admin": True, "editor": False, "viewer": False},
                }
            }
        )

        self.init_flows()
        self.prompt_icon_path.mkdir(parents=True, exist_ok=True)

    def deinit(self):
        log.info('De-initializing')

    # def init_db(self):
    #     log.info("DB init")
    #     from .models.all import (
    #         Prompt,
    #         PromptVersion,
    #         PromptMessage,
    #         PromptVariable,
    #         PromptVersionTagAssociation,
    #         SearchRequest,
    #     )
    #     project_list = self.context.rpc_manager.call.project_list(filter_={'create_success': True})
    #     for i in project_list:
    #         log.info("Creating missing tables in project %s", i['id'])
    #         with db.with_project_schema_session(i['id']) as tenant_db:
    #             db.get_all_metadata().create_all(bind=tenant_db.connection())
    #             tenant_db.commit()

    def init_flows(self):
        from .flows import prompt, prompt_validate
