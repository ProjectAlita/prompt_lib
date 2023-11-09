from pylon.core.tools import log, web

from tools import VaultClient


class Event:

    @web.event("new_ai_user")
    def handle_new_ai_user(self, context, event, payload: dict):
        # payload == {user_id: int, user_email: str}
        secrets = VaultClient().get_all_secrets()
        allowed_domains = {i.strip().strip('@') for i in secrets.get('ai_project_allowed_domains', '').split(',')}
        user_email_domain = payload.get('user_email', '').split('@')[-1]
        log.info(
            'Checking if user eligible to join special project. %s with domain |%s| in allowed domains |%s| and result is |%s|',
            payload.get('user_email'),
            user_email_domain,
            allowed_domains,
            user_email_domain in allowed_domains
        )
        if user_email_domain in allowed_domains:
            log.info('Adding epam user to project %s', payload)
            try:
                ai_project_id = secrets['ai_project_id']
            except KeyError:
                log.critical('Secret for "ai_project_id" is not set')
                return

            try:
                ai_project_roles = secrets['ai_project_roles']
            except KeyError:
                project_secrets = VaultClient(ai_project_id).get_all_secrets()
                try:
                    ai_project_roles = project_secrets['ai_project_roles']
                except KeyError:
                    log.critical('Secret for "ai_project_roles" is not set')
                    return
            ai_project_roles = [i.strip() for i in ai_project_roles.split(',')]
            log.info('Adding epam user %s to project %s with roles %s', payload, ai_project_id, ai_project_roles)

            context.rpc_manager.call.admin_add_user_to_project(
                ai_project_id, payload['user_id'], ai_project_roles
            )
        else:
            log.warning('User with non-epam email registered %s', payload)
