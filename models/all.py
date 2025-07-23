from datetime import datetime

from tools import db_tools, db, config as c

from sqlalchemy import Integer, String, DateTime, func, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from ...promptlib_shared.models.all import AbstractLikesMixin
from ...promptlib_shared.models.enums.all import PublishStatus


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
    datasources: Mapped[dict] = mapped_column(JSONB, nullable=True)
    applications: Mapped[dict] = mapped_column(JSONB, nullable=True)
    status: Mapped[PublishStatus] = mapped_column(String, nullable=False, default=PublishStatus.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # reference fields to origin
    shared_owner_id: Mapped[int] = mapped_column(Integer, nullable=True)
    shared_id: Mapped[int] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchRequest(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "search_requests"
    __table_args__ = (
        {"schema": c.POSTGRES_TENANT_SCHEMA},
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_keyword: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
