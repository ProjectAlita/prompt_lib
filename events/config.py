from pylon.core.tools import log, web

from tools import VaultClient


class Event:

    @web.event("new_ai_user")
    def handle_new_ai_user(self, context, event, payload: dict):
        # payload == {user_id: int, user_email: str}
        secrets = VaultClient().get_all_secrets()
        allowed_domains = {i.strip().strip('@') for i in secrets.get('ai_project_allowed_domains', '').split(',')}
        user_email_domain = payload.get('user_email', '').split('@')[-1]
        #
        user_allowed = "*" in allowed_domains or user_email_domain in allowed_domains
        #
        log.info(
            'Checking if user eligible to join special project. %s with domain |%s| in allowed domains |%s| and result is |%s|',
            payload.get('user_email'),
            user_email_domain,
            allowed_domains,
            user_allowed,
        )
        #
        if user_allowed:
            log.info('Adding AI user to project %s', payload)
            try:
                ai_project_id = secrets['ai_project_id']
            except KeyError:
                log.critical('Secret for "ai_project_id" is not set')
                return
            #
            try:
                ai_project_roles = secrets['ai_project_roles']
            except KeyError:
                project_secrets = VaultClient(ai_project_id).get_all_secrets()
                try:
                    ai_project_roles = project_secrets['ai_project_roles']
                except KeyError:
                    log.critical('Secret for "ai_project_roles" is not set')
                    return
            #
            global_admin_role = "admin"
            global_user_roles = context.rpc_manager.call.auth_get_user_roles(
                payload['user_id']
            )
            #
            ai_moderator_role = "editor"  # get from ai_public_admin_role?
            ai_project_roles = [i.strip() for i in ai_project_roles.split(',')]
            #
            if self.descriptor.config.get("admins_are_moderators", False) and \
                    global_admin_role in global_user_roles:
                ai_project_roles.append(ai_moderator_role)
            #
            log.info('Adding AI user %s to project %s with roles %s', payload, ai_project_id, ai_project_roles)
            #
            context.rpc_manager.call.admin_add_user_to_project(
                ai_project_id, payload['user_id'], ai_project_roles
            )
        else:
            log.warning('User with non-AI email registered %s', payload)
