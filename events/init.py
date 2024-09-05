import json

from pylon.core.tools import log, web
from tools import VaultClient

applications_roles = [
    "models.applications.applications.list",
    "models.applications.applications.create",
    "models.applications.version.details",
    "models.applications.version.update",
    "models.applications.version.delete",
    "models.applications.application.details",
    "models.applications.application.delete",
    "models.applications.application.update",
    "models.applications.predict.post",
    "models.applications.task.get",
    "models.applications.task.delete",
    "models.applications.tool.details",
    "models.applications.tool.delete",
    "models.applications.tool.update",
    "models.applications.tools.list",
    "models.applications.tools.create",
    "models.applications.versions.get",
    "models.applications.versions.create"
]


class Event:

    @web.event("pylon_modules_initialized")
    def handle_pylon_modules_initialized(self, context, event, payload):
        _ = context, event
        #
        event_pylon_id = payload
        if self.context.id != event_pylon_id:
            return
        #
        if self.descriptor.config.get("auto_setup", False):
            log.info("Performing post-init setup checks")
            # Data
            setup_roles = {
                "prompt_lib_moderators": [
                    "models.prompt_lib.approve.post",
                    "models.prompt_lib.approve_collection.post",
                    "models.prompt_lib.reject.post",
                    "models.prompt_lib.reject_collection.delete",
                    "models.prompts",
                    "projects.projects.project.view"
                ],
                "prompt_lib_public": [
                    "models.datasource",
                    "models.datasources",
                    "models.datasources.dataset.details",
                    "models.datasources.datasource.details",
                    "models.datasources.predict.post",
                    "models.datasources.public_datasources.list",
                    "models.datasources.search.post",
                    "models.datasources.version.details",
                    "models.datasources.versions.get",
                    "models.prompt_lib",
                    "models.prompt_lib.author.detail",
                    "models.prompt_lib.collection.details",
                    "models.prompt_lib.collections.list",
                    "models.prompt_lib.export_import.export",
                    "models.prompt_lib.export_import.import",
                    "models.prompt_lib.predict.post",
                    "models.prompt_lib.prompt.details",
                    "models.prompt_lib.prompts.list",
                    "models.prompt_lib.prompts.search",
                    "models.prompt_lib.public_collection.details",
                    "models.prompt_lib.public_prompt.details",
                    "models.prompt_lib.public_prompts.list",
                    "models.prompt_lib.search_requests.list",
                    "models.prompt_lib.tags.list",
                    "models.prompt_lib.trending_authors.list",
                    "models.prompt_lib.version.details",
                    "models.prompts",
                    "projects.projects.project.view",
                    "models.prompt_lib.feedbacks.create",
                    #
                    "models.applications.public_applications.list",
                    # "models.chat.conversations.list",
                ],
                "public_admin": [
                    "models.datasource",
                    "models.datasource.publish.post",
                    "models.datasource.unpublish.delete",
                    "models.datasources",
                    "models.datasources.dataset.delete",
                    "models.datasources.dataset.details",
                    "models.datasources.dataset.update",
                    "models.datasources.dataset_status.details",
                    "models.datasources.datasource.delete",
                    "models.datasources.datasource.details",
                    "models.datasources.datasources.create",
                    "models.datasources.datasources.list",
                    "models.datasources.datasources.update",
                    "models.datasources.deduplicate.post",
                    "models.datasources.predict.post",
                    "models.datasources.public_datasources.list",
                    "models.datasources.search.post",
                    "models.datasources.version.delete",
                    "models.datasources.version.details",
                    "models.datasources.version.update",
                    "models.datasources.versions.create",
                    "models.datasources.versions.get",
                    *applications_roles
                ]
            }
            #
            setup_secrets = {
                "ai_project_allowed_domains": self.descriptor.config.get(
                    "ai_project_allowed_domains", ""
                ),
                "ai_project_roles": "prompt_lib_public",  # change to viewer after redo
                "ai_public_admin_role": "public_admin",  # change to editor after redo
                "ai_project_api_url": "",
                "ai_storage_quota": json.dumps({
                    "default": self.descriptor.config.get(
                        "ai_storage_default_quota", None
                    ),
                }),
            }
            # Check and create secrets
            vault_client = VaultClient()
            secrets = vault_client.get_all_secrets()
            secrets_changed = False
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
                    roles=["system"],
                )
                #
                if public_project_id is not None:
                    # Save ID to secrets
                    secrets["ai_project_id"] = public_project_id
                    secrets_changed = True
            # Apply/add correct permissions (keep extra manually added for now)
            if "ai_project_id" in secrets:
                public_project_id = int(secrets["ai_project_id"])
                #
                for role, permissions in setup_roles.items():
                    role_item = self.context.rpc_manager.call.admin_get_role(
                        project_id=public_project_id,
                        role_name=role,
                    )
                    #
                    if not role_item:
                        log.info("Adding role: %s", role)
                        #
                        self.context.rpc_manager.call.admin_add_role(
                            project_id=public_project_id,
                            role_names=[role],
                        )
                        #
                        self.context.rpc_manager.call.admin_set_permissions_for_role(
                            project_id=public_project_id,
                            role_name=role,
                            permissions=permissions,
                        )
                    else:
                        role_perms = self.context.rpc_manager.call.admin_get_permissions_for_role(
                            project_id=public_project_id,
                            role_name=role,
                        )
                        missing_permissions = list(set(permissions) - set(role_perms))
                        #
                        log.info("Adding new/missing permissions for role: %s -> %s", role, missing_permissions)
                        #
                        self.context.rpc_manager.call.admin_add_permissions_for_role(
                            project_id=public_project_id,
                            role_name=role,
                            permissions=missing_permissions,
                        )
            # Save secrets if changes are made
            if secrets_changed:
                vault_client.set_secrets(secrets)
            # Activate personal project schedule
            self.context.rpc_manager.call.scheduling_make_active(
                "projects_create_personal_project",
                True,
            )
