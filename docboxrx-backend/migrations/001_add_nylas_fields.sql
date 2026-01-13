-- Database migration to add Nylas integration fields
-- Run this to update existing messages table with new columns

-- Add Nylas integration fields to messages table
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS grant_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS provider_message_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS thread_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS provider VARCHAR(50);

-- Add full email content fields
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS raw_body TEXT,
ADD COLUMN IF NOT EXISTS raw_body_html TEXT,
ADD COLUMN IF NOT EXISTS raw_headers TEXT;

-- Add metadata and attachments fields (PostgreSQL)
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS metadata JSONB,
ADD COLUMN IF NOT EXISTS attachments JSONB,
ADD COLUMN IF NOT EXISTS has_attachments BOOLEAN DEFAULT FALSE;

-- Add status and tracking fields
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active',
ADD COLUMN IF NOT EXISTS read_status BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS starred BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS important BOOLEAN DEFAULT FALSE;

-- Add AI processing fields
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS recommended_action VARCHAR(255),
ADD COLUMN IF NOT EXISTS action_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS draft_reply TEXT,
ADD COLUMN IF NOT EXISTS llm_fallback BOOLEAN DEFAULT FALSE;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_grant_id ON messages(grant_id);
CREATE INDEX IF NOT EXISTS idx_messages_provider_message_id ON messages(provider_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_read_status ON messages(read_status);

-- Create webhooks table
CREATE TABLE IF NOT EXISTS webhooks (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    grant_id VARCHAR(255),
    webhook_url VARCHAR(500) NOT NULL,
    webhook_secret VARCHAR(255),
    events JSONB,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_triggered TIMESTAMP,
    trigger_count INTEGER DEFAULT 0,
    filters JSONB,
    headers JSONB
);

-- Create webhook indexes
CREATE INDEX IF NOT EXISTS idx_webhooks_user_id ON webhooks(user_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_grant_id ON webhooks(grant_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_active ON webhooks(active);
