from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Database URL - use environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Convert postgres:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    parts = urlsplit(DATABASE_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    if sslmode and sslmode.lower() == "require":
        connect_args["ssl"] = True
    DATABASE_URL = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

# For SQLite, we need aiosqlite
if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=connect_args)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    practice_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="user", cascade="all, delete-orphan")
    corrections = relationship("Correction", back_populates="user", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    sender = Column(String, nullable=False)
    sender_domain = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    snippet = Column(Text, nullable=True)
    zone = Column(String, nullable=False)  # STAT, TODAY, THIS_WEEK, LATER
    confidence = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
    jone5_message = Column(String, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    classified_at = Column(DateTime, default=datetime.utcnow)
    corrected = Column(Boolean, default=False)
    corrected_at = Column(DateTime, nullable=True)
    source_id = Column(String, nullable=True)
    source_name = Column(String, nullable=True)
    
    # Nylas integration fields
    grant_id = Column(String, nullable=True, index=True)  # Link to Nylas grant
    provider_message_id = Column(String, nullable=True, index=True)  # Original message ID from provider
    thread_id = Column(String, nullable=True, index=True)  # Email thread ID
    provider = Column(String, nullable=True)  # google, microsoft, etc.
    
    # Full email content
    raw_body = Column(Text, nullable=True)  # Full plain text body
    raw_body_html = Column(Text, nullable=True)  # Full HTML body
    raw_headers = Column(Text, nullable=True)  # Raw email headers
    
    # Metadata and attachments
    email_metadata = Column(JSON, nullable=True)  # Additional metadata
    attachments = Column(JSON, nullable=True)  # Attachment info
    has_attachments = Column(Boolean, default=False)
    
    # Status and tracking
    status = Column(String, default='active')  # active, archived, deleted
    read = Column(Boolean, default=False)
    starred = Column(Boolean, default=False)
    important = Column(Boolean, default=False)
    
    # AI processing fields
    summary = Column(Text, nullable=True)  # AI-generated summary
    recommended_action = Column(String, nullable=True)  # AI-recommended action
    action_type = Column(String, nullable=True)  # reply, forward, call, etc.
    draft_reply = Column(Text, nullable=True)  # Auto-generated reply draft
    llm_fallback = Column(Boolean, default=False)  # Whether LLM fallback was used
    
    user = relationship("User", back_populates="messages")

class Source(Base):
    __tablename__ = "sources"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    inbound_token = Column(String, unique=True, nullable=False, index=True)
    inbound_address = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    email_count = Column(Integer, default=0)
    
    user = relationship("User", back_populates="sources")

class Correction(Base):
    __tablename__ = "corrections"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    old_zone = Column(String, nullable=False)
    new_zone = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    corrected_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="corrections")

class RuleOverride(Base):
    __tablename__ = "rule_overrides"
    
    id = Column(String, primary_key=True)
    sender_key = Column(String, unique=True, nullable=False, index=True)  # e.g., "sender:email@example.com"
    zone = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# CloudMailin messages (for the public endpoint)
class CloudMailinMessage(Base):
    __tablename__ = "cloudmailin_messages"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, default="cloudmailin-default-user")
    sender = Column(String, nullable=False)
    sender_domain = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    snippet = Column(Text, nullable=True)
    zone = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
    jone5_message = Column(String, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    classified_at = Column(DateTime, default=datetime.utcnow)
    corrected = Column(Boolean, default=False)
    source_id = Column(String, default="cloudmailin")
    source_name = Column(String, default="CloudMailin")

class Webhook(Base):
    __tablename__ = "webhooks"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    grant_id = Column(String, nullable=True, index=True)  # Link to specific Nylas grant
    webhook_url = Column(String, nullable=False)  # External webhook URL
    webhook_secret = Column(String, nullable=True)  # Secret for verification
    events = Column(JSON, nullable=True)  # List of events to subscribe to
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    
    # Processing metadata
    webhook_filters = Column(JSON, nullable=True)  # Event filters
    webhook_headers = Column(JSON, nullable=True)  # Custom headers to send
    
    user = relationship("User", back_populates="webhooks")

# Add webhooks relationship to User
User.webhooks = relationship("Webhook", back_populates="user", cascade="all, delete-orphan")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
