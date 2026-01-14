
-- Phase A: Database Migration for Message State Vectors
CREATE TABLE IF NOT EXISTS message_state_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nylas_message_id TEXT UNIQUE NOT NULL,
    grant_id TEXT NOT NULL,

    -- The Vector: (A, O, D, R, C, L)
    intent_label TEXT,           -- [A] Clinical, Billing, Admin, etc.
    current_owner_id UUID,       -- [O] Who owns this task
    deadline_at TIMESTAMP,       -- [D] Fibonacci-based escalation
    risk_score FLOAT DEFAULT 0.0, -- [R] 0.0 to 1.0
    context_blob JSONB DEFAULT '{}', -- [C] Patient/Billing context
    lifecycle_state TEXT DEFAULT 'NEW', -- [L] NEW, WAITING, COMPLETED, OVERDUE

    subject TEXT,
    snippet TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES message_state_vectors(id),
    event_type TEXT NOT NULL, -- CREATED, STATE_CHANGED, OWNER_CHANGED
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
