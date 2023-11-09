from pylon.core.tools import web, log

from tools import auth, theme, VaultClient


class Slot:  # pylint: disable=E1101,R0903

    @web.slot('models_config_content')
    @auth.decorators.check_slot(['models.config'],
                                access_denied_reply=theme.access_denied_part)
    def content(self, context, slot, payload):
        readme = VaultClient(payload.project.id).get_all_secrets().get('ai_project_readme')
        with context.app.app_context():
            return self.descriptor.render_template(
                'config/content.html',
                payload=payload,
                readme=readme,
            )

    @web.slot('models_config_scripts')
    @auth.decorators.check_slot(['models.config'])
    def scripts(self, context, slot, payload):
        with context.app.app_context():
            return self.descriptor.render_template(
                'config/scripts.html',
            )

    @web.slot('models_config_styles')
    @auth.decorators.check_slot(['models.config'])
    def styles(self, context, slot, payload):
        with context.app.app_context():
            return self.descriptor.render_template(
                'config/styles.html',
            )
