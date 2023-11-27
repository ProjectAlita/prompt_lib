from datetime import datetime
from typing import List

from tools import db_tools, db, rpc_tools, config as c
from pylon.core.tools import log

from .enums.all import PromptVersionStatus, PromptVersionType, MessageRoles
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    func,
    ForeignKey,
    JSON,
    Table,
    Column,
    UniqueConstraint,
    MetaData,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref


class Prompt(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "prompts"
    __table_args__ = ({"schema": c.POSTGRES_TENANT_SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    versions: Mapped[List["PromptVersion"]] = relationship(
        back_populates="prompt", lazy=True, cascade="all, delete"
    )
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def get_latest_version(self):
        return next(version for version in self.versions if version.name == "latest")


class PromptVersion(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "name", name="_prompt_name_uc"),
        {"schema": c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompts.id")
    )
    prompt: Mapped["Prompt"] = relationship(back_populates="versions", lazy=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    commit_message: Mapped[str] = mapped_column(String, nullable=True)
    type: Mapped[PromptVersionType] = mapped_column(
        String(64), nullable=False, default=PromptVersionType.chat
    )
    status: Mapped[PromptVersionStatus] = mapped_column(
        String, nullable=False, default=PromptVersionStatus.draft
    )
    context: Mapped[str] = mapped_column(String, nullable=True)
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variables: Mapped[List["PromptVariable"]] = relationship(
        back_populates="prompt_version", lazy=True, cascade="all, delete-orphan"
    )
    messages: Mapped[List["PromptMessage"]] = relationship(
        back_populates="prompt_version",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="PromptMessage.id",
    )
    tags: Mapped[List["PromptTag"]] = relationship(
        secondary=lambda: PromptVersionTagAssociation,
        backref="prompt_version",
        lazy="joined",
    )
    model_settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    embedding_settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class PromptVariable(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "prompt_variables"
    __table_args__ = (
        UniqueConstraint("prompt_version_id", "name", name="_version_name_uc"),
        {"schema": c.POSTGRES_TENANT_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_version_id: Mapped[int] = mapped_column(
        ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id")
    )
    prompt_version: Mapped["PromptVersion"] = relationship(
        back_populates="variables", lazy=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )


class PromptMessage(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "prompt_messages"
    __table_args__ = ({"schema": c.POSTGRES_TENANT_SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_version_id: Mapped[int] = mapped_column(
        ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id")
    )
    prompt_version: Mapped["PromptVersion"] = relationship(
        back_populates="messages", lazy=True
    )
    role: Mapped[MessageRoles] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )
    custom_content: Mapped[dict] = mapped_column(JSON, nullable=True)
    # todo: add order


class PromptTag(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "prompt_tags"
    __table_args__ = ({"schema": c.POSTGRES_TENANT_SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # prompt_versions: Mapped[List['PromptVersion']] = relationship(secondary=lambda: PromptVersionTagAssociation, lazy=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=True)
    # from_public = Column(Boolean, nullable=False, default=False)


# log.info(f'db.Base.metadata, {db.Base.metadata}')
PromptVersionTagAssociation = Table(
    "prompt_version_tag_association",
    db.Base.metadata,
    Column("version_id", ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id")),
    Column("tag_id", ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompt_tags.id")),
    schema=c.POSTGRES_TENANT_SCHEMA,
)

# PromptVersionCollectionAssociation = Table(
#     "prompt_version_collection_association",
#     db.Base.metadata,
#     Column("version_id", ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompt_versions.id")),
#     Column(
#         "collection_id", ForeignKey(f"{c.POSTGRES_TENANT_SCHEMA}.prompt_collections.id")
#     ),
#     schema=c.POSTGRES_TENANT_SCHEMA,
# )


class Collection(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "prompt_collections"
    __table_args__ = ({"schema": c.POSTGRES_TENANT_SCHEMA},)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # prompts: Mapped[List["PromptVersion"]] = relationship(
    #     secondary=lambda: PromptVersionCollectionAssociation,
    #     backref="collections",
    #     lazy="joined",
    # )
    prompts: Mapped[dict] = mapped_column(JSON, nullable=True)
