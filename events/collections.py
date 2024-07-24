from copy import deepcopy

from sqlalchemy import and_, or_

from pylon.core.tools import log, web
from tools import db
from ..models.all import Collection
from ..models.enums.all import CollectionPatchOperations
from ..models.pd.collections import CollectionItem
from ..utils.collection_registry import (
    ENTITY_REG,
    get_entity_info_by_name
)
from ..utils.collections import (
    CollectionPublishing,
    add_entity_to_collection,
    fire_patch_collection_event,
    group_by_project_id,
    remove_entity_from_collection,
)
from ..utils.publish_utils import get_public_project_id
from ...promptlib_shared.models.enums.all import PublishStatus


class Event:
    @web.event("prompt_public_collection_status_change")
    def handle_collection_status_change(self, context, event, payload: dict):
        log.info(f'Event {payload}')
        private_project_id = payload['private_project_id']
        private_collection_id = payload['private_collection_id']
        status = payload['status']

        CollectionPublishing.set_status(
            project_id=private_project_id,
            collection_id=private_collection_id,
            status=status
        )

    @web.event("prompt_lib_collection_updated")
    def handle_collection_updated(self, context, event, payload: dict):
        added_entities = payload['added_entities']
        removed_entities = payload['removed_entities']
        collection_data = payload['collection_data']
        public_id = get_public_project_id()

        entity_info = get_entity_info_by_name(payload['entity_name'])
        Entity = entity_info.get_entity_type()

        # add collection to entities
        grouped_added_entities: dict = group_by_project_id(added_entities, data_type="tuple")
        for owner_id, ids in grouped_added_entities.items():
            add_collection_to_entities(Entity, owner_id, ids, collection_data, context)

        # remove collection from entities
        grouped_removed_entities: dict = group_by_project_id(removed_entities, data_type="tuple")
        for owner_id, ids in grouped_removed_entities.items():
            delete_collection_from_entities(Entity, owner_id, ids, collection_data, context)

        # synchronize private and public collections
        if public_id != collection_data['owner_id']:
            synchronize_collections(
                collection_data,
                entity_info.entities_name,
                Entity,
                added_entities,
                removed_entities
            )

    @web.event("prompt_lib_collection_deleted")
    def handle_collection_deleted(self, context, event, payload: dict):
        collection_data = payload

        for ent in ENTITY_REG:
            entities = group_by_project_id(collection_data[ent.entities_name])
            for owner_id, ids in entities.items():
                delete_collection_from_entities(
                    ent.get_entity_type(),
                    owner_id,
                    ids,
                    collection_data,
                    context
                )

    @web.event("prompt_lib_collection_added")
    def handle_collection_added(self, context, event, payload: dict):
        collection_data = payload

        for ent in ENTITY_REG:
            entities = group_by_project_id(collection_data[ent.entities_name])
            for owner_id, ids in entities.items():
                add_collection_to_entities(ent.get_entity_type(), owner_id, ids, collection_data, context)

    @web.event('prompt_lib_entity_published')
    def handle_entity_publishing(self, context, event, payload: dict) -> None:
        entity_data = payload['entity_data']
        owner_id = entity_data['owner_id']
        collections = payload['collections']
        entity_name = payload['entity_name']
        entity_info = get_entity_info_by_name(entity_name)

        with db.with_project_schema_session(owner_id) as session:
            if not collections:
                collections = session.query(Collection).filter(
                    or_(
                        *[
                            and_(
                                Collection.shared_id == collection['id'],
                                Collection.shared_owner_id == collection['owner_id']
                            ) for collection in collections
                        ]
                    )
                ).all()
            else:
                collections = []

            for collection in collections:
                entities = deepcopy(entity_info.get_entities_field(collection))
                entities.append({
                    "owner_id": owner_id,
                    "id": entity_data['id']
                })
                setattr(collection, entity_info.entities_name, entities)
            session.commit()

            for collection in collections:
                fire_patch_collection_event(
                    collection.to_json(),
                    CollectionPatchOperations.add,
                    entity_data,
                    entity_name
                )

    @web.event('prompt_lib_collection_unpublished')
    def handle_collection_unpublished(self, context, event, payload) -> None:
        private_id = payload.get('private_id')
        private_owner_id = payload.get('private_owner_id')
        with db.with_project_schema_session(private_owner_id) as session:
            collection = session.query(Collection).get(private_id)
            if not collection:
                return
            collection.status = PublishStatus.draft
            session.commit()


def delete_collection_from_entities(entity_type, owner_id: int, ids: list, collection_data: dict, context):
    with db.get_session(owner_id) as session:
        for entity in session.query(entity_type).filter(entity_type.id.in_(ids)).all():
            new_data = [
                deepcopy(collection) for collection in entity.collections
                if (collection['owner_id'] != collection_data['owner_id'] or
                    collection['id'] != collection_data['id'])
            ]
            entity.collections = new_data

        session.commit()


def add_collection_to_entities(entity_type, owner_id: int, ids: list, collection_data: dict, context):
    with db.get_session(owner_id) as session:
        for entity in session.query(entity_type).filter(entity_type.id.in_(ids)).all():
            new_data: list = deepcopy(entity.collections)
            new_data.append({
                "owner_id": collection_data['owner_id'],
                "id": collection_data['id']
            })
            entity.collections = new_data

        session.commit()


def synchronize_collections(
    private_collection_data, entities_name, entity_type,
    added_entities: list = None, removed_entities: list = None
):
    added_entities = added_entities or []
    removed_entities = removed_entities or []
    public_id = get_public_project_id()
    with db.with_project_schema_session(public_id) as session:
        collection = session.query(Collection).filter_by(
            shared_owner_id=private_collection_data['owner_id'],
            shared_id=private_collection_data['id']
        ).first()

        if not collection:
            return

        added_entities = find_public_entities(entity_type, added_entities, session)
        removed_entities = find_public_entities(entity_type, removed_entities, session)

        for entity in added_entities:
            entity = CollectionItem(id=entity.id, owner_id=entity.owner_id)
            add_entity_to_collection(collection, entities_name, entity, return_data=False)

        for entity in removed_entities:
            entity = CollectionItem(id=entity.id, owner_id=entity.owner_id)
            remove_entity_from_collection(collection, entities_name, entity, return_data=False)

        session.commit()


def find_public_entities(entity_type, entities: list, session):
    if not entities:
        return []

    public_id = get_public_project_id()
    public_entities = filter(lambda x: x[0] == public_id, entities)
    private_entities = filter(lambda x: x[0] != public_id, entities)

    return session.query(entity_type).filter(
        or_(
            *[
                and_(
                    entity_type.shared_id == entity[1],
                    entity_type.shared_owner_id == entity[0]
                ) for entity in private_entities
            ],
            *[
                and_(
                    entity_type.id == data[1],
                ) for data in public_entities
            ]
        )
    ).all()
