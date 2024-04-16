from abc import ABCMeta, abstractmethod
from json import loads
from datetime import datetime
from typing import List, Dict
from sqlalchemy import func, cast, String, or_
from sqlalchemy.orm import joinedload

from tools import db, rpc_tools
from pylon.core.tools import log

from .like_utils import add_likes, add_trending_likes, add_my_liked
from ..models.all import Collection, Prompt, PromptVersion, PromptVersionTagAssociation
from ...promptlib_shared.models.all import Tag


class TagListABC(ABCMeta):
    meta_registry = {}

    def __new__(mcs, name, bases, attrs):
        resulting_class = super().__new__(mcs, name, bases, attrs)
        if bases:  # exlcuding parent class
            name = name.split('TagList')[0].lower()
            mcs.meta_registry[name] = resulting_class
        return resulting_class


class TagList(metaclass=TagListABC):
    def __init__(self, project_id, args):
        self.project_id = project_id
        self.args = args
        self._set_general_query_info()
        # trending period
        self._set_trending_info()
        self.session = db.get_project_schema_session(project_id)
        self._is_collection = False

    def _set_general_query_info(self):
        self.limit = self.args.get("limit", default=10, type=int)
        self.offset = self.args.get("offset", default=0, type=int)
        self.my_liked = self.args.get("my_liked", default=False, type=bool)
        self.entity_coverage = self.args.get("entity_coverage", default="all")
        self.not_all = self.entity_coverage != "all"

    def _set_trending_info(self):
        trend_start_period = self.args.get('trend_start_period')
        trend_end_period = self.args.get('trend_end_period')
        self.trend_period = None
        if trend_start_period:
            trend_end_period = datetime.utcnow() if not trend_end_period else datetime.strptime(trend_end_period, "%Y-%m-%dT%H:%M:%S")
            trend_start_period = datetime.strptime(trend_start_period, "%Y-%m-%dT%H:%M:%S")
            self.trend_period = (trend_start_period, trend_end_period)

    @abstractmethod
    def set_related_entity_info(self):
        pass

    def get_related_entity_filters(self):
        filters = []
        if author_id := self.args.get('author_id'):
            filters.append(self.Entity.versions.any(self.Version.author_id == author_id))
        if statuses := self.args.get('statuses'):
            statuses = statuses.split(',')
            filters.append(self.Entity.versions.any(self.Version.status.in_(statuses)))
        if query := self.args.get('query'):
            filters.append(
                or_(
                    self.Entity.name.ilike(f"%{query}%"),
                    self.Entity.description.ilike(f"%{query}%")
                )
            )
        return filters

    def add_related_entity_extra_filters(self, filters):
        return filters

    def get_related_entity_query(self, filters):
        entity_query = (
            self.session.query(self.Entity)
            .options(joinedload(self.Entity.versions))
        )
        extra_columns = []
        entity_query, new_columns = add_likes(
            original_query=entity_query,
            project_id=self.project_id,
            entity=self.Entity
        )
        extra_columns.extend(new_columns)
        if self.trend_period:
            entity_query, new_columns = add_trending_likes(
                original_query=entity_query,
                project_id=self.project_id,
                trend_period=self.trend_period,
                filter_results=True,
                entity=self.Entity,
            )
            extra_columns.extend(new_columns)
        if self.my_liked:
            entity_query, new_columns = add_my_liked(
                original_query=entity_query,
                project_id=self.project_id,
                filter_results=True,
                entity=self.Entity
            )
            extra_columns.extend(new_columns)
        if filters:
            entity_query = entity_query.filter(*filters)

        entity_query = entity_query.with_entities(self.Entity.id)
        return entity_query.subquery()

    def get_main_query_filters(self, entity_subquery):
        tag_filters = [getattr(self.Version, self.foriegn_key).in_(entity_subquery)]
        if search := self.args.get("search"):
            tag_filters.append(Tag.name.ilike(f"%{search}%"))
        if self._is_collection:
            all_prompt_ids = [
                prompt['id'] for collection in self.session.query(Collection.prompts).all()
                for prompt in next(iter(collection))
            ]
            tag_filters.append(getattr(self.Version, self.foriegn_key).in_(all_prompt_ids))
        return tag_filters

    def execute_main_query(self, tag_filters):
        select_list = [Tag.id, Tag.name, cast(Tag.data, String)]
        if self.not_all:
            select_list.append(func.count(func.distinct(getattr(self.Version, self.foriegn_key))))

        query = (
            self.session.query(*select_list)
            .filter(*tag_filters)
        )
        if self.not_all:
            query = query.join(self.VersionTagAssociation, self.VersionTagAssociation.c.tag_id == Tag.id)\
                .join(self.Version, self.Version.id == self.VersionTagAssociation.c.version_id)

        query = query.group_by(Tag.id, Tag.name, cast(Tag.data, String))
        order_by = Tag.id.desc()
        if self.not_all:
            order_by = func.count(func.distinct(getattr(self.Version, self.foriegn_key))).desc()
        query = query.order_by(order_by)
        total = query.count()

        if self.limit:
            query = query.limit(self.limit)
        if self.offset:
            query = query.offset(self.offset)

        return total, query.all()
    
    def _as_dict(self, x):
        result = {'id': x[0], 'name': x[1], 'data': loads(x[2])}
        if self.not_all:
            result[self.count_name] = x[3]
        return result

    # template method    
    def get_tags(self):
        # set entity info
        tag_filters = []
        if self.not_all:
            self.set_related_entity_info()

            # getting related entity info
            filters = self.get_related_entity_filters()

            # adding extra filters into filters
            filters = self.add_related_entity_extra_filters(filters)

            # get related entity query
            subquery = self.get_related_entity_query(filters)

            # get main query filters
            tag_filters = self.get_main_query_filters(subquery)

        # execute main query
        total, tags = self.execute_main_query(tag_filters)

        result = {
            "total": total,
            "rows": [self._as_dict(tag) for tag in tags]
        }
        self.session.close()
        return result


class PromptTagList(TagList):
    def _flatten_prompt_ids(self, project_id: int, collection_prompts: List[Dict[str, int]]):
        prompt_ids = []
        for collection_prompt in collection_prompts:
            prompts = collection_prompt[0]
            for prompt in prompts:
                if prompt['owner_id'] == project_id:
                    prompt_ids.append(prompt['id'])
        return prompt_ids
    
    def add_related_entity_extra_filters(self, filters):
        if collection_phrase := self.args.get('collection_phrase'):
            collection_prompts = self.session.query(Collection.prompts).filter(
                or_(
                    Collection.name.ilike(f"%{collection_phrase}%"),
                    Collection.description.ilike(f"%{collection_phrase}%")
                )
            ).all()
            prompt_ids = prompt_ids = self._flatten_prompt_ids(self.project_id, collection_prompts)
            filters.append(Prompt.id.in_(prompt_ids))

        if self.args.get("my_liked_collections", default=False, type=bool):
            query = self.session.query(Collection.prompts)
            extra_columns = []

            query, new_columns = add_likes(
                original_query=query,
                project_id=self.project_id,
                entity=Collection,
            )
            extra_columns.extend(new_columns)
            query, new_columns = add_my_liked(
                original_query=query,
                project_id=self.project_id,
                entity=Collection,
                filter_results=True
            )
            extra_columns.extend(new_columns)
            q_result = query.all()
            prompt_ids = self._flatten_prompt_ids(self.project_id, q_result)
            filters.append(Prompt.id.in_(prompt_ids))
        
        return filters

    def set_related_entity_info(self):
        self.Entity = Prompt
        self.Version = PromptVersion
        self.VersionTagAssociation = PromptVersionTagAssociation
        self.foriegn_key = "prompt_id"
        self.count_name = "prompt_count"


class DatasourceTagList(TagList):
    def __init__(self, project_id, args):
        super().__init__(project_id, args)
        self.rpc = rpc_tools.RpcMixin().rpc.call

    def set_related_entity_info(self):
        self.Entity = self.rpc.datasources_get_datasource_model()
        self.Version = self.rpc.datasources_get_version_model()
        self.VersionTagAssociation = self.rpc.datasources_get_version_association_model()
        self.foriegn_key = 'datasource_id'
        self.count_name = "datasource_count"


class ApplicationTagList(TagList):
    def __init__(self, project_id, args):
        super().__init__(project_id, args)
        self.rpc = rpc_tools.RpcMixin().rpc.call

    def set_related_entity_info(self):
        self.Entity = self.rpc.applications_get_application_model()
        self.Version = self.rpc.applications_get_version_model()
        self.VersionTagAssociation = self.rpc.applications_get_version_association_model()
        self.foriegn_key = 'application_id'
        self.count_name = "application_count"


class CollectionTagList(TagList):
    def set_related_entity_info(self):
        self._is_collection = True
        self.Entity = Prompt
        self.Version = PromptVersion
        self.VersionTagAssociation = PromptVersionTagAssociation
        self.foriegn_key = 'prompt_id'
        self.count_name = "prompt_count"


class AllTagList(TagList):
    def set_related_entity_info(self):
        pass


def list_tags(project_id, args):
    entity_coverage = args.get("entity_coverage", default="all")
    TagClass: TagList = TagListABC.meta_registry.get(entity_coverage)
    if not TagClass:
        return {
            "total": 0,
            "rows": list()
        }
    return TagClass(project_id, args).get_tags()
    