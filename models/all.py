from datetime import datetime
from typing import List

from tools import db_tools, db, config as c

from .enums.all import PromptVersionType, MessageRoles
from sqlalchemy import Integer, String, DateTime, func, ForeignKey, JSON, Table, Column, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from ...promptlib_shared.models.all import AbstractLikesMixin, Tag
from ...promptlib_shared.models.enums.all import PublishStatus


class Prompt(db_tools.AbstractBaseMixin, db.Base, AbstractLikesMixin):
    __tablename__ = 'prompts'
    __table_args__ = (
        UniqueConstraint('shared_owner_id', 'shared_id', name='_shared_origin'),
        {'schema': c.POSTGRES_TENANT_SCHEMA},
    )
    likes_entity_name: str = 'prompt'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    versions: Mapped[List['PromptVersion']] = relationship(back_populates='prompt', lazy=True,
                                                           cascade='all, delete',
                                                           order_by='PromptVersion.created_at.desc()')
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    shared_owner_id: Mapped[int] = mapped_column(Integer, nullable=True)
    shared_id: Mapped[int] = mapped_column(Integer, nullable=True)
    collections: Mapped[list] = mapped_column(JSONB, nullable=True, default=list)

    def get_latest_version(self):
        return next(version for version in self.versions if version.name == 'latest')


class PromptVersion(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'prompt_versions'
    __table_args__ = (
        UniqueConstraint('shared_owner_id', 'shared_id', name='_version_shared_origin'),
        UniqueConstraint('prompt_id', 'name', name='_prompt_name_uc'),
        {'schema': c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey(f'{c.POSTGRES_TENANT_SCHEMA}.prompts.id'))
    prompt: Mapped['Prompt'] = relationship(back_populates='versions', lazy=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    commit_message: Mapped[str] = mapped_column(String, nullable=True)
    type: Mapped[PromptVersionType] = mapped_column(String(64), nullable=False, default=PromptVersionType.chat)
    status: Mapped[PublishStatus] = mapped_column(String, nullable=False, default=PublishStatus.draft)
    context: Mapped[str] = mapped_column(String, nullable=True)
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variables: Mapped[List['PromptVariable']] = relationship(back_populates='prompt_version', lazy=True,
                                                             cascade='all, delete-orphan')
    messages: Mapped[List['PromptMessage']] = relationship(back_populates='prompt_version', lazy=True,
                                                           cascade='all, delete-orphan', order_by='PromptMessage.id')
    tags: Mapped[List[Tag]] = relationship(secondary=lambda: PromptVersionTagAssociation,
                                           backref='prompt_version', lazy='joined')
    model_settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    embedding_settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # reference fields to origin 
    shared_owner_id: Mapped[int] = mapped_column(Integer, nullable=True)
    shared_id: Mapped[int] = mapped_column(Integer, nullable=True)
    conversation_starters: Mapped[dict] = mapped_column(JSON, default=list)
    welcome_message: Mapped[str] = mapped_column(String, default='')


class PromptVariable(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'prompt_variables'
    __table_args__ = (
        UniqueConstraint('prompt_version_id', 'name', name='_prompt_version_variable_name_uc'),
        {'schema': c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_version_id: Mapped[int] = mapped_column(ForeignKey(f'{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id'))
    prompt_version: Mapped['PromptVersion'] = relationship(back_populates='variables', lazy=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class PromptMessage(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = 'prompt_messages'
    __table_args__ = ({'schema': c.POSTGRES_TENANT_SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_version_id: Mapped[int] = mapped_column(ForeignKey(f'{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id'))
    prompt_version: Mapped['PromptVersion'] = relationship(back_populates='messages', lazy=True)
    role: Mapped[MessageRoles] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, onupdate=func.now())
    custom_content: Mapped[dict] = mapped_column(JSON, nullable=True)
    # todo: add order


PromptVersionTagAssociation = Table(
    'prompt_version_tag_association',
    db.Base.metadata,
    Column('version_id', ForeignKey(f'{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id')),
    Column('tag_id', ForeignKey(f'{c.POSTGRES_TENANT_SCHEMA}.{Tag.__tablename__}.id')),
    schema=c.POSTGRES_TENANT_SCHEMA
)


class Collection(db_tools.AbstractBaseMixin, db.Base, AbstractLikesMixin):
    __tablename__ = "prompt_collections"
    __table_args__ = (
        UniqueConstraint('shared_owner_id', 'shared_id', name='_collection_shared_origin'),
        {"schema": c.POSTGRES_TENANT_SCHEMA},
    )
    likes_entity_name: str = 'collection'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prompts: Mapped[dict] = mapped_column(JSONB, nullable=True)
    status: Mapped[PublishStatus] = mapped_column(String, nullable=False, default=PublishStatus.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # reference fields to origin 
    shared_owner_id: Mapped[int] = mapped_column(Integer, nullable=True)
    shared_id: Mapped[int] = mapped_column(Integer, nullable=True)


class SearchRequest(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "search_requests"
    __table_args__ = (
        {"schema": c.POSTGRES_TENANT_SCHEMA},
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_keyword: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
