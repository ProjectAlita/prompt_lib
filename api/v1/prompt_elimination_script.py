from typing import List, Optional

from flask import request
from pydantic import BaseModel, ValidationError
from tools import api_tools, auth, db, serialize, db_tools, config as c, rpc_tools
from sqlalchemy import text

from ...models.all import Prompt, Collection, PromptVersion

from pylon.core.tools import log


class EliminatePromptPayload(BaseModel):
    project_ids: Optional[List[int]] = None
    flush: bool = False


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.prompt_elimination.create"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": False, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": False, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def post(self):
        payload = dict(request.json)

        try:
            eliminate_prompt_payload = EliminatePromptPayload.parse_obj(payload)
        except ValidationError as e:
            return e.errors(), 400

        def get_all_project_ids():
            return [
                i['id'] for i in self.module.context.rpc_manager.call.project_list(
                    filter_={'create_success': True}
                )
            ]

        project_ids = eliminate_prompt_payload.project_ids or get_all_project_ids()
        project_ids.sort()
        results = list()
        errors = list()

        rpc = rpc_tools.RpcMixin().rpc.call
        application_model = rpc.applications_get_application_model()
        application_version_model = rpc.applications_get_version_model()
        application_variable_model = rpc.applications_get_variable_model()
        application_tag_model = rpc.applications_get_version_association_model()

        for pid in project_ids:
            with db.get_session(pid) as session:
                if eliminate_prompt_payload.flush:
                    prompts = session.query(Prompt).all()
                    for prompt in prompts:
                        session.delete(prompt)

                    collections = session.query(Collection).all()
                    for collection in collections:
                        collection.prompts = []
                    session.commit()
                    continue
                try:
                    session.execute(
                        text(f'ALTER TABLE p_{pid}.prompts ADD COLUMN IF NOT EXISTS new_agent_id INTEGER')
                    )
                    session.execute(
                        text(f'ALTER TABLE p_{pid}.prompt_versions ADD COLUMN IF NOT EXISTS new_agent_version_id INTEGER')
                    )
                    session.commit()
                    prompt_query = session.query(Prompt)
                    collection_query = session.query(Collection)
                    application_tags = []
                    for prompt in prompt_query.yield_per(100):
                        application = application_model(
                            name=prompt.name,
                            description=prompt.description,
                            created_at=prompt.created_at,
                            shared_id=prompt.shared_id,
                            owner_id=prompt.owner_id,
                            shared_owner_id=prompt.shared_owner_id,
                            collections=prompt.collections,
                        )
                        session.add(application)
                        for prompt_version in prompt.versions:
                            llm_settings = prompt_version.model_settings
                            model_settings = llm_settings.pop('model')
                            llm_settings['model_name'] = model_settings['model_name']
                            llm_settings['integration_uid'] = model_settings['integration_uid']
                            application_version = application_version_model(
                                name=prompt_version.name,
                                author_id=prompt_version.author_id,
                                status=prompt_version.status,
                                created_at=prompt_version.created_at,
                                shared_id=prompt_version.shared_id,
                                shared_owner_id=prompt_version.shared_owner_id,
                                conversation_starters=prompt_version.conversation_starters,
                                welcome_message=prompt_version.welcome_message,
                                instructions=prompt_version.context,
                                llm_settings=llm_settings,
                                meta=prompt_version.meta,
                                application=application,
                            )
                            application_variables = [
                                application_variable_model(
                                    application_version=application_version,
                                    application_version_id=application_version.id,
                                    name=prompt_var.name,
                                    value=prompt_var.value,
                                    created_at=prompt_var.created_at,
                                    updated_at=prompt_var.updated_at,
                                ) for prompt_var in prompt_version.variables
                            ]
                            application_version.variables = application_variables
                            session.add(application_version)
                            session.flush()
                            application_tags.extend([
                                {'version_id': application_version.id, 'tag_id': prompt_tag.id}
                                for prompt_tag in prompt_version.tags
                            ])
                            session.execute(
                                text(f"""
                                        UPDATE p_{pid}.prompt_versions
                                        SET new_agent_version_id = :new_agent_version_id
                                        WHERE id = :prompt_version_id
                                    """),
                                {
                                    'new_agent_version_id': application_version.id,
                                    'prompt_version_id': prompt_version.id
                                }
                            )

                        session.execute(
                            text(f"""
                                UPDATE p_{pid}.prompts
                                SET new_agent_id = :new_agent_id
                                WHERE id = :prompt_id
                            """),
                            {
                                'new_agent_id': application.id,
                                'prompt_id': prompt.id
                            }
                        )

                    # migrate collections
                    for collection in collection_query.yield_per(100):
                        if collection.prompts:
                            new_application_items = []
                            for prompt_entry in collection.prompts:
                                prompt_id = prompt_entry.get("id")
                                if prompt_id:
                                    # Use raw SQL to fetch the new_agent_id from the database
                                    result = session.execute(
                                        text(f"""
                                            SELECT new_agent_id
                                            FROM p_{pid}.prompts
                                            WHERE id = :prompt_id
                                        """),
                                        {'prompt_id': prompt_id}
                                    ).fetchone()

                                    # Check if the result exists and contains a valid new_agent_id
                                    if result and result.new_agent_id:
                                        new_application_items.append({
                                            "id": result.new_agent_id,
                                            "owner_id": prompt_entry.get("owner_id")
                                        })

                            collection.applications = new_application_items
                            session.add(collection)

                    session.execute(application_tag_model.insert().values(application_tags))
                    session.commit()
                except Exception as e:
                    session.rollback()
                    log.error(f'Project ID {pid}, error: {str(e)}')
                    errors.append({'project_id': pid, 'error': str(e)})

        return {'results': serialize(results), 'errors': serialize(errors)}, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '',
    ])

    mode_handlers = {
        c.ADMINISTRATION_MODE: PromptLibAPI,
    }
