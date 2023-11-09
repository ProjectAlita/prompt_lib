from pylon.core.tools import web, log  # pylint: disable=E0611,E0401

from tools import auth, theme  # pylint: disable=E0401


class Slot:  # pylint: disable=E1101,R0903

    @web.slot('prompts_content')
    @auth.decorators.check_slot(["models.prompts"],
                                access_denied_reply=theme.access_denied_part)
    def content(self, context, slot, payload):
        ai_integrations = context.rpc_manager.call.integrations_get_all_integrations_by_section(
            context.rpc_manager.call.project_get_id(), "ai"
        )
        ai_integrations = [integration.dict(
            exclude={'section'}
        ) for integration in ai_integrations]

        with context.app.app_context():
            return self.descriptor.render_template(
                'content.html',
                integrations=ai_integrations,
            )

    @web.slot('prompts_scripts')
    @auth.decorators.check_slot(["models.prompts"])
    def scripts(self, context, slot, payload):
        with context.app.app_context():
            return self.descriptor.render_template(
                'scripts.html',
            )

    @web.slot('prompts_styles')
    @auth.decorators.check_slot(["models.prompts"])
    def styles(self, context, slot, payload):
        with context.app.app_context():
            return self.descriptor.render_template(
                'styles.html',
            )
