from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MessageStateVector(Base):
    __tablename__ = "message_state_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    nylas_message_id = Column(String, unique=True, nullable=False)
    grant_id = Column(String, nullable=False)

    intent_label = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    context_blob = Column(JSONB, server_default='{}')
    summary = Column(String, nullable=True)

    current_owner_role = Column(String, nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)

    lifecycle_state = Column(String, server_default="NEW")
    is_overdue = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    events = relationship("MessageEvent", back_populates="vector", cascade="all, delete-orphan")


class MessageEvent(Base):
    __tablename__ = "message_events"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    vector_id = Column(UUID(as_uuid=True), ForeignKey("message_state_vectors.id", ondelete="CASCADE"))
    event_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vector = relationship("MessageStateVector", back_populates="events")
