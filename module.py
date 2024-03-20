from pylon.core.tools import module, log

from tools import db, theme, VaultClient


class Module(module.ModuleModel):
    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

    def init(self):
        self.descriptor.init_all()
        self.init_db()
        #
        if self.descriptor.config.get("auto_setup", False):
            # Check and create secrets
            vault_client = VaultClient()
            secrets = vault_client.get_all_secrets()
            secrets_changed = False
            #
            setup_secrets = {
                "ai_project_allowed_domains": self.descriptor.config.get(
                    "ai_project_allowed_domains", ""
                ),
                "ai_project_roles": "viewer",
                "ai_public_admin_role": "editor",
            }
            #
            for key, value in setup_secrets.items():
                if key not in secrets:
                    secrets[key] = value
                    secrets_changed = True
            # Create public project
            system_user = "system@centry.user"
            try:
                system_user_id = self.context.rpc_manager.call.auth_get_user(
                    email=system_user,
                )["id"]
            except:  # pylint: disable=W0702
                system_user_id = None
            #
            if "ai_project_id" not in secrets and system_user_id is not None:
                #
                public_project_name = self.descriptor.config.get(
                    "public_project_name",
                    "promptlib_public",
                )
                #
                public_project_id = self.context.rpc_manager.call.projects_create_project(
                    project_name=public_project_name,
                    plugins=["configuration", "models"],
                    admin_email=system_user,
                    owner_id=system_user_id,
                    roles=["editor", "viewer"],
                )
                #
                if public_project_id is not None:
                    secrets["ai_project_id"] = public_project_id
                    secrets_changed = True
            # Save secrets if changes are made
            if secrets_changed:
                vault_client.set_secrets(secrets)
            # Activate personal project schedule
            self.context.rpc_manager.call.scheduling_make_active(
                "projects_create_personal_project",
                True,
            )
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

    def deinit(self):
        log.info('De-initializing')

    def init_db(self):
        from .models.all import (
            Prompt, PromptVersion,
            PromptTag, PromptMessage,
            PromptVariable, PromptVersionTagAssociation,
            SearchRequest,
        )
        project_list = self.context.rpc_manager.call.project_list()
        for i in project_list:
            with db.with_project_schema_session(i['id']) as tenant_db:
                db.get_all_metadata().create_all(bind=tenant_db.connection())
                tenant_db.commit()

    def init_flows(self):
        from .flows import prompt, prompt_validate
