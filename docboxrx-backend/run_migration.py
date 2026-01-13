import os
import psycopg2
from psycopg2 import sql

def run_migration():
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Connect to the database
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    try:
        # Enable UUID extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        
        # Create message_state_vectors table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_state_vectors (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                nylas_message_id TEXT UNIQUE NOT NULL,
                grant_id TEXT NOT NULL,
                
                -- The Vector (AI Analysis)
                intent_label TEXT NOT NULL,
                risk_score FLOAT NOT NULL,
                context_blob JSONB DEFAULT '{}',
                summary TEXT,
                
                -- The Routing
                current_owner_role TEXT,
                deadline_at TIMESTAMP,
                
                -- The Lifecycle
                lifecycle_state TEXT DEFAULT 'NEW',
                is_overdue BOOLEAN DEFAULT FALSE,
                
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Create message_events table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_events (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                vector_id UUID REFERENCES message_state_vectors(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vectors_lifecycle ON message_state_vectors(lifecycle_state);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vectors_risk ON message_state_vectors(risk_score DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vectors_deadline ON message_state_vectors(deadline_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_vector_id ON message_events(vector_id);")
        
        # Commit changes
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        # Rollback in case of error
        conn.rollback()
        print(f"Error during migration: {e}")
        raise
        
    finally:
        # Close connections
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_migration()