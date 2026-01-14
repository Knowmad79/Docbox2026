# DOCBOX DATABASE SCHEMA
# Shared schema specification for all AI agents

## CORE MODELS

### User
```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # UUID
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    practice_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    grants = relationship("NylasGrant", back_populates="user", cascade="all, delete-orphan")
    webhooks = relationship("Webhook", back_populates="user", cascade="all, delete-orphan")
```

### NylasGrant
```python
class NylasGrant(Base):
    __tablename__ = "nylas_grants"
    
    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    grant_id = Column(String, nullable=False, unique=True, index=True)  # From Nylas
    email = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)  # google, microsoft, yahoo, imap
    
    # Token storage (encrypted)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(String, nullable=True)
    token_type = Column(String, nullable=True)
    scope = Column(String, nullable=True)
    
    # Metadata
    provider_folders = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="grants")
    messages = relationship("Message", back_populates="grant")
    webhooks = relationship("Webhook", back_populates="grant")
```

### Message
```python
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Basic email info
    sender = Column(String, nullable=False)
    sender_domain = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    snippet = Column(Text, nullable=True)
    
    # AI classification
    zone = Column(String, nullable=False, index=True)  # STAT, TODAY, THIS_WEEK, LATER
    confidence = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
    jone5_message = Column(String, nullable=False)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    classified_at = Column(DateTime, default=datetime.utcnow)
    corrected = Column(Boolean, default=False)
    corrected_at = Column(DateTime, nullable=True)
    
    # Source tracking
    source_id = Column(String, nullable=True)
    source_name = Column(String, nullable=True)
    
    # Nylas integration
    grant_id = Column(String, ForeignKey("nylas_grants.id"), nullable=True, index=True)
    provider_message_id = Column(String, nullable=True, index=True)
    thread_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=True)
    
    # Full email content
    raw_body = Column(Text, nullable=True)
    raw_body_html = Column(Text, nullable=True)
    raw_headers = Column(Text, nullable=True)
    
    # Metadata and attachments
    metadata = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    has_attachments = Column(Boolean, default=False)
    
    # Status and tracking
    status = Column(String, default='active', index=True)  # active, archived, deleted
    read = Column(Boolean, default=False, index=True)
    starred = Column(Boolean, default=False, index=True)
    important = Column(Boolean, default=False)
    
    # AI processing fields
    summary = Column(Text, nullable=True)
    recommended_action = Column(String, nullable=True)
    action_type = Column(String, nullable=True)
    draft_reply = Column(Text, nullable=True)
    llm_fallback = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="messages")
    grant = relationship("NylasGrant", back_populates="messages")
```

## AI PROCESSING MODELS

### MessageStateVector
```python
class MessageStateVector(Base):
    __tablename__ = "message_state_vectors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    nylas_message_id = Column(String, unique=True, nullable=False, index=True)
    grant_id = Column(String, nullable=False, index=True)
    
    # AI analysis
    intent_label = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False, index=True)
    context_blob = Column(JSONB, server_default='{}')
    summary = Column(String, nullable=True)
    
    # Routing and ownership
    current_owner_role = Column(String, nullable=True, index=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Lifecycle
    lifecycle_state = Column(String, server_default="NEW", index=True)
    is_overdue = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    events = relationship("MessageEvent", back_populates="vector", cascade="all, delete-orphan")
```

### MessageEvent
```python
class MessageEvent(Base):
    __tablename__ = "message_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    vector_id = Column(UUID(as_uuid=True), ForeignKey("message_state_vectors.id", ondelete="CASCADE"))
    
    event_type = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    vector = relationship("MessageStateVector", back_populates="events")
```

## WEBHOOK AND INTEGRATION MODELS

### Webhook
```python
class Webhook(Base):
    __tablename__ = "webhooks"
    
    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    grant_id = Column(String, ForeignKey("nylas_grants.id"), nullable=True, index=True)
    
    # Webhook configuration
    webhook_url = Column(String, nullable=False)
    webhook_secret = Column(String, nullable=True)
    events = Column(JSON, nullable=True)  # ["message.created", "message.updated"]
    
    # Status and tracking
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    
    # Processing metadata
    filters = Column(JSON, nullable=True)
    headers = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="webhooks")
    grant = relationship("NylasGrant", back_populates="webhooks")
```

### CloudMailinMessage
```python
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
```

## LEGACY MODELS (for compatibility)

### Source
```python
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
```

### Correction
```python
class Correction(Base):
    __tablename__ = "corrections"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    old_zone = Column(String, nullable=False)
    new_zone = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    corrected_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="corrections")
```

### RuleOverride
```python
class RuleOverride(Base):
    __tablename__ = "rule_overrides"
    
    id = Column(String, primary_key=True)
    sender_key = Column(String, unique=True, nullable=False, index=True)
    zone = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## INDEXES FOR PERFORMANCE

```sql
-- User and grant indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_nylas_grants_user_id ON nylas_grants(user_id);
CREATE INDEX idx_nylas_grants_grant_id ON nylas_grants(grant_id);
CREATE INDEX idx_nylas_grants_email ON nylas_grants(email);

-- Message indexes
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_grant_id ON messages(grant_id);
CREATE INDEX idx_messages_zone ON messages(zone);
CREATE INDEX idx_messages_received_at ON messages(received_at);
CREATE INDEX idx_messages_sender_domain ON messages(sender_domain);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_read ON messages(read);
CREATE INDEX idx_messages_starred ON messages(starred);

-- State vector indexes
CREATE INDEX idx_message_state_vectors_grant_id ON message_state_vectors(grant_id);
CREATE INDEX idx_message_state_vectors_risk_score ON message_state_vectors(risk_score);
CREATE INDEX idx_message_state_vectors_lifecycle_state ON message_state_vectors(lifecycle_state);
CREATE INDEX idx_message_state_vectors_deadline_at ON message_state_vectors(deadline_at);

-- Webhook indexes
CREATE INDEX idx_webhooks_user_id ON webhooks(user_id);
CREATE INDEX idx_webhooks_grant_id ON webhooks(grant_id);
CREATE INDEX idx_webhooks_active ON webhooks(active);
```

## MIGRATION SEQUENCE

1. **001_add_nylas_fields.sql** - Add Nylas integration to messages
2. **002_create_nylas_grants.sql** - Create grants table
3. **003_create_state_vectors.sql** - Create AI processing tables
4. **004_create_webhooks.sql** - Create webhook management
5. **005_add_indexes.sql** - Performance indexes
6. **006_migrate_legacy_data.sql** - Migrate from old schema

## RELATIONSHIP MAP

```
User (1) → (N) Message
User (1) → (N) NylasGrant
User (1) → (N) Webhook
User (1) → (N) Source (legacy)

NylasGrant (1) → (N) Message
NylasGrant (1) → (N) Webhook

Message (1) → (1) MessageStateVector
MessageStateVector (1) → (N) MessageEvent
```

## ENVIRONMENT VARIABLES

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Nylas
NYLAS_API_KEY=your_nylas_api_key
NYLAS_CLIENT_ID=your_nylas_client_id
NYLAS_API_URI=https://api.us.nylas.com
NYLAS_CALLBACK_URI=https://yourdomain.com/api/nylas/callback

# AI
CEREBRAS_API_KEY=your_cerebras_api_key

# Security
SECRET_KEY=your_jwt_secret_key
DOCBOX_ENCRYPTION_KEY=your_encryption_key
```
