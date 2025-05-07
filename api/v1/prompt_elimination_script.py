import json
import os
import shutil
from typing import List, Optional

from flask import request
from pydantic import BaseModel, ValidationError
from tools import api_tools, auth, db, serialize, db_tools, config as c, rpc_tools, this
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
                            new_meta = prompt_version.meta or {}
                            if "icon_meta" in new_meta and new_meta["icon_meta"]:
                                new_meta["icon_meta"]["url"] = new_meta["icon_meta"]["url"].replace(
                                    "prompt_lib/prompt_icon", "applications/application_icon"
                                )
                            # TODO migrate messages?
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
                                meta=new_meta,
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
                            # First query: Update the `chat_participant_mapping` table
                            # DO NOT CHANGE ORDER OF QUERIES
                            # TODO migrate chat icon meta
                            # new_meta = prompt_version.meta or {}
                            # if "icon_meta" in new_meta and new_meta["icon_meta"]:
                            #     new_meta["icon_meta"]["url"] = new_meta["icon_meta"]["url"].replace(
                            #         "prompt_lib/prompt_icon", "applications/application_icon"
                            #     )
                            session.execute(
                                text(f"""
                                    UPDATE p_{pid}.chat_participant_mapping
                                    SET entity_settings = jsonb_build_object(
                                        'icon_meta', entity_settings->'icon_meta',
                                        'variables', entity_settings->'variables',
                                        'version_id', {application_version.id},
                                        'llm_settings', jsonb_build_object(
                                            'top_k', entity_settings->'model_settings'->'top_k',
                                            'top_p', entity_settings->'model_settings'->'top_p',
                                            'max_tokens', entity_settings->'model_settings'->'max_tokens',
                                            'model_name', entity_settings->'model_settings'->'model'->>'model_name',
                                            'temperature', entity_settings->'model_settings'->'temperature',
                                            'integration_uid', entity_settings->'model_settings'->'model'->>'integration_uid'
                                        ),
                                        'chat_history_template', COALESCE(entity_settings->>'chat_history_template', 'all')
                                    )
                                    WHERE participant_id IN (
                                        SELECT id
                                        FROM p_{pid}.chat_participants
                                        WHERE (entity_meta->>'id')::int = {prompt.id} AND entity_name = 'prompt'
                                    );
                                """)
                            )
                            # Second query: Update the `chat_participants` table
                            session.execute(
                                text(f"""
                                            UPDATE p_{pid}.chat_participants
                                            SET entity_name = 'application',
                                                entity_meta = jsonb_set(entity_meta, '{{id}}', '{json.dumps(application.id)}'::jsonb)
                                            WHERE (entity_meta->>'id')::int = {prompt.id} AND entity_name = 'prompt';
                                        """)
                            )
                            # Update alita_tools, change `type` column and modify the `settings` JSONB field
                            session.execute(
                                text(f"""
                                    UPDATE p_{pid}.alita_tools
                                    SET type = 'application',
                                        settings = (
                                            settings
                                            || jsonb_build_object(
                                                'application_version_id', '{str(application_version.id)}'::jsonb,
                                                'application_id', '{str(application.id)}'::jsonb,
                                                'selected_tools', '[]'::jsonb
                                            )
                                        )
                                        - 'prompt_version_id'
                                        - 'prompt_id'
                                    WHERE type = 'prompt'
                                      AND settings->>'prompt_version_id' = '{str(prompt_version.id)}';
                                """)
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

        for pid in project_ids:
            with db.get_session(pid) as session:
                try:
                    # Migrate forks
                    prompt_version_query = session.query(PromptVersion)
                    for prompt_version in prompt_version_query.all():
                        # Check if the prompt version has fork metadata in its meta field
                        if prompt_version.meta and "parent_project_id" in prompt_version.meta:
                            parent_project_id = prompt_version.meta["parent_project_id"]
                            parent_entity_id = prompt_version.meta["parent_entity_id"]
                            parent_entity_version_id = prompt_version.meta["parent_entity_version_id"]
                            parent_author_id = prompt_version.meta["parent_author_id"]

                            # Fetch the parent application's new_agent_id and new_agent_version_id from the parent project
                            parent_new_agent_id = None
                            parent_new_agent_version_id = None
                            with db.get_session(parent_project_id) as parent_session:
                                # Fetch the parent prompt's new_agent_id
                                parent_result = parent_session.execute(
                                    text(f"""
                                                    SELECT new_agent_id
                                                    FROM p_{parent_project_id}.prompts
                                                    WHERE id = :parent_entity_id
                                                """),
                                    {'parent_entity_id': parent_entity_id}
                                ).fetchone()
                                log.debug(f'{parent_result=}')

                                # Fetch the parent prompt version's new_agent_version_id
                                parent_version_result = parent_session.execute(
                                    text(f"""
                                                    SELECT new_agent_version_id
                                                    FROM p_{parent_project_id}.prompt_versions
                                                    WHERE id = :parent_entity_version_id
                                                """),
                                    {'parent_entity_version_id': parent_entity_version_id}
                                ).fetchone()
                                log.debug(f'{parent_version_result=}')

                                if parent_result and parent_result.new_agent_id:
                                    parent_new_agent_id = parent_result.new_agent_id
                                    log.debug(f'{parent_new_agent_id=}')

                                if parent_version_result and parent_version_result.new_agent_version_id:
                                    parent_new_agent_version_id = parent_version_result.new_agent_version_id
                                    log.debug(f'{parent_new_agent_version_id=}')

                            # If the parent application exists, update the meta field of the current application version
                            if parent_new_agent_id and parent_new_agent_version_id:
                                # Fetch the existing application version for the current prompt version
                                new_agent_version_id_q = session.execute(
                                    text(f"""
                                        SELECT new_agent_version_id
                                        FROM p_{pid}.prompt_versions
                                        WHERE id = :prompt_version_id
                                    """),
                                    {'prompt_version_id': prompt_version.id}
                                ).fetchone()
                                current_result = parent_session.execute(
                                    text(f"""
                                        SELECT id, meta
                                        FROM p_{pid}.application_versions
                                        WHERE id = :current_agent_version_id
                                    """),
                                    {'current_agent_version_id': new_agent_version_id_q.new_agent_version_id}
                                ).fetchone()

                                log.debug(f'{current_result=}')

                                if current_result:
                                    current_agent_version_id = current_result.id
                                    current_meta = current_result.meta or {}

                                    # Update the meta field with parent application version information
                                    new_meta = {
                                        "parent_entity_id": parent_new_agent_id,
                                        "parent_entity_version_id": parent_new_agent_version_id,
                                        "parent_author_id": parent_author_id,
                                        "parent_project_id": parent_project_id,
                                    }
                                    current_meta.update(new_meta)
                                    log.debug(f'{new_meta=}')

                                    session.execute(
                                        text(f"""
                                                        UPDATE p_{pid}.application_versions
                                                        SET meta = :meta
                                                        WHERE id = :current_agent_version_id
                                                    """),
                                        {
                                            'meta': json.dumps(current_meta),
                                            'current_agent_version_id': current_agent_version_id
                                        }
                                    )
                    session.commit()
                except Exception as e:
                    session.rollback()
                    log.error(f'Project ID {pid}, error: {str(e)}')
                    errors.append({'project_id': pid, 'error': str(e)})

        for project_id in project_ids:
            prompt_path = this.descriptor.config.get("prompt_icon_path", "/data/static/prompt_icon")
            application_path = prompt_path.replace('prompt_icon', 'application_icon')
            prompt_project_path = os.path.join(prompt_path, str(project_id))
            application_project_path = os.path.join(application_path, str(project_id))

            if not os.path.isdir(prompt_project_path):
                continue

            if not os.path.exists(application_project_path):
                os.makedirs(application_project_path)
                log.debug(f"Created project folder in application_icon: {application_project_path}")

            for file_name in os.listdir(prompt_project_path):
                prompt_file_path = os.path.join(prompt_project_path, file_name)
                application_file_path = os.path.join(application_project_path, file_name)

                if not os.path.isfile(prompt_file_path):
                    continue

                if os.path.exists(application_file_path):
                    log.debug(f"File already exists, skipping: {application_file_path}")
                    continue

                shutil.copy2(prompt_file_path, application_file_path)
                log.debug(f"Copied {prompt_file_path} to {application_file_path}")

        return {'errors': serialize(errors)}, 201


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '',
    ])

    mode_handlers = {
        c.ADMINISTRATION_MODE: PromptLibAPI,
    }
