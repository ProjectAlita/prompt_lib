from pylon.core.tools import module, log

from tools import db


class Module(module.ModuleModel):
    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

    def init(self):
        self.descriptor.init_all()

        self.init_db()

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
