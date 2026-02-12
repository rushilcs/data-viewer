"""SQLAlchemy models per docs/02-data-model.md."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    BigInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship("User", back_populates="org")
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="org")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")  # admin, viewer, publisher
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization", back_populates="users")
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="created_by_user")
    dataset_access_grants: Mapped[list["DatasetAccess"]] = relationship(
        "DatasetAccess", foreign_keys="DatasetAccess.user_id", back_populates="user"
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")  # draft, published, archived
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    org: Mapped["Organization"] = relationship("Organization", back_populates="datasets")
    created_by_user: Mapped["User"] = relationship("User", back_populates="datasets")
    items: Mapped[list["Item"]] = relationship("Item", back_populates="dataset")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="dataset")
    annotations: Mapped[list["Annotation"]] = relationship("Annotation", back_populates="dataset")
    access_entries: Mapped[list["DatasetAccess"]] = relationship(
        "DatasetAccess", back_populates="dataset", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_datasets_org_status_created", "org_id", "status", "created_at"),)


class DatasetAccess(Base):
    """Dataset-level ACL: which users can see a dataset (viewer role sees only shared datasets)."""
    __tablename__ = "dataset_access"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")  # viewer | editor
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="access_entries")
    user: Mapped["User"] = relationship("User", back_populates="dataset_access_grants", foreign_keys=[user_id])
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        Index("ix_dataset_access_org_user", "org_id", "user_id"),
        Index("ix_dataset_access_org_dataset", "org_id", "dataset_id"),
        UniqueConstraint("dataset_id", "user_id", name="uq_dataset_access_dataset_user"),
    )


class Invite(Base):
    """Invite token for signup: email + org + role; one-time use (legacy; open signup uses pending_dataset_share)."""
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")  # viewer | publisher
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization")
    created_by_user: Mapped["User"] = relationship("User")


class PendingDatasetShare(Base):
    """Dataset shared with an email that doesn't have an account yet; applied when they sign up."""
    __tablename__ = "pending_dataset_share"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    access_role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization")
    dataset: Mapped["Dataset"] = relationship("Dataset")
    created_by_user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("dataset_id", "email", name="uq_pending_dataset_share_dataset_email"),
        Index("ix_pending_dataset_share_org_email", "org_id", "email"),
    )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="items")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="item")
    annotations: Mapped[list["Annotation"]] = relationship("Annotation", back_populates="item")

    __table_args__ = (
        Index("ix_items_org_dataset_created", "org_id", "dataset_id", "created_at"),
        Index("ix_items_org_dataset_type_created", "org_id", "dataset_id", "type", "created_at"),
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # image, video, audio, other
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="assets")
    item: Mapped["Item | None"] = relationship("Item", back_populates="assets")

    __table_args__ = (Index("ix_assets_org_dataset_item", "org_id", "dataset_id", "item_id"),)


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    schema: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    org: Mapped["Organization"] = relationship("Organization")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="annotations")
    item: Mapped["Item"] = relationship("Item", back_populates="annotations")

    __table_args__ = (Index("ix_annotations_org_item", "org_id", "item_id"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
