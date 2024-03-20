from pylon.core.tools import log, web
from tools import VaultClient


class Event:

    @web.event("pylon_modules_initialized")
    def handle_new_ai_user(self, context, event, payload):
        _ = context, event
        #
        event_pylon_id = payload
        if self.context.id != event_pylon_id:
            return
        #
        if self.descriptor.config.get("auto_setup", False):
            log.info("Performing post-init setup checks")
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
                "ai_project_api_url": "",
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
