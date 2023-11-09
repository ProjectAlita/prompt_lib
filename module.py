from pylon.core.tools import module, log

from tools import db, theme


class Module(module.ModuleModel):
    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

    def init(self):
        self.descriptor.init_all()

        self.init_db()

        # try:
        #     theme.register_section(
        #         "models",
        #         "Models",
        #         kind="holder",
        #         location="left",
        #         permissions={
        #             "permissions": ["models"],
        #             "recommended_roles": {
        #                 "administration": {"admin": True, "editor": True, "viewer": True},
        #                 "default": {"admin": True, "editor": True, "viewer": True},
        #             }
        #         }
        #     )
        # except (ValueError, RuntimeError):
        #     ...

        # theme.register_subsection(
        #     "models", "prompts",
        #     "Prompts",
        #     title="AI Prompts",
        #     kind="slot",
        #     prefix="prompts_",
        #     weight=5,
        #     permissions={
        #         "permissions": ["models.prompts"],
        #         "recommended_roles": {
        #             "administration": {"admin": True, "editor": True, "viewer": True},
        #             "default": {"admin": True, "editor": True, "viewer": True},
        #         }
        #     }
        # )

        # theme.register_subsection(
        #     "models", "config",
        #     "Config",
        #     title="Config",
        #     kind="slot",
        #     prefix="models_config_",
        #     # weight=5,
        #     permissions={
        #         "permissions": ["models.config"],
        #         "recommended_roles": {
        #             "administration": {"admin": True, "editor": False, "viewer": False},
        #             "default": {"admin": True, "editor": False, "viewer": False},
        #         }
        #     }
        # )

        self.init_flows()

    def deinit(self):
        log.info('De-initializing')

    def init_db(self):
        from .models.all import (
            Prompt, PromptVersion,
            PromptTag, PromptMessage,
            PromptVariable, PromptVersionTagAssociation
        )
        project_list = self.context.rpc_manager.call.project_list()
        for i in project_list:
            with db.with_project_schema_session(i['id']) as tenant_db:
                db.get_all_metadata().create_all(bind=tenant_db.connection())
                tenant_db.commit()

    def init_flows(self):
        from .flows import prompt, prompt_validate
