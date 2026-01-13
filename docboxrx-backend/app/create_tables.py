import os
import asyncio
import asyncpg
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

MIGRATION_SQL = """
CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";

CREATE TABLE IF NOT EXISTS message_state_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nylas_message_id TEXT UNIQUE NOT NULL,
    grant_id TEXT NOT NULL,

    intent_label TEXT NOT NULL,
    risk_score FLOAT NOT NULL,
    context_blob JSONB DEFAULT '{}',
    summary TEXT,

    current_owner_role TEXT,
    deadline_at TIMESTAMP,

    lifecycle_state TEXT DEFAULT 'NEW',
    is_overdue BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vectors_lifecycle ON message_state_vectors(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_vectors_risk ON message_state_vectors(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_vectors_deadline ON message_state_vectors(deadline_at);

CREATE TABLE IF NOT EXISTS message_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vector_id UUID REFERENCES message_state_vectors(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


async def run_migration() -> None:
    if not DATABASE_URL:
        print(f"ERROR: DATABASE_URL not found. Checked path: {env_path}")
        return

    print("Connecting to Database...")
    url = DATABASE_URL.replace("postgres://", "postgresql://")

    try:
        conn = await asyncpg.connect(url)
        print("Connected. Running Migration...")

        await conn.execute(MIGRATION_SQL)

        print("Migration Complete! Tables 'message_state_vectors' and 'message_events' created.")
        await conn.close()

    except Exception as e:
        print(f"Migration Failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_migration())
