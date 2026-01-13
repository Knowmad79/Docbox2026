"""Database module for persistent storage using PostgreSQL or SQLite."""
import base64
import json
import os
import uuid
from datetime import datetime, timedelta
import hashlib
from contextlib import contextmanager
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Check if we have a PostgreSQL DATABASE_URL
# Fail fast if DATABASE_URL is not set in environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required - set in .env (local) or Fly secrets (prod)")

USE_POSTGRES = DATABASE_URL.startswith("postgres")

if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
else:
    import sqlite3

# Use /data directory on Fly.io for persistent storage, or local file for dev
DB_PATH = os.environ.get("DATABASE_PATH", "/data/docboxrx.db" if os.path.exists("/data") else "./docboxrx.db")

# Global connection pool for Postgres to avoid repeated connection overhead
_pg_pool = None
_sqlite_conn = None
_token_key = hashlib.sha256((os.environ.get("DOCBOX_ENCRYPTION_KEY") or os.environ.get("SECRET_KEY") or "docboxrx-default").encode("utf-8")).digest()


def _xor_cipher(value: bytes) -> bytes:
    """Apply a simple XOR cipher using the derived token key."""
    return bytes(b ^ _token_key[i % len(_token_key)] for i, b in enumerate(value))


def encrypt_token(value: str | None) -> str | None:
    """Encrypt a sensitive token using a reversible XOR + base64 scheme."""
    if value is None:
        return None
    encrypted = _xor_cipher(value.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("utf-8")


def decrypt_token(value: str | None) -> str | None:
    """Decrypt a sensitive token previously stored with encrypt_token."""
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value.encode("utf-8"))
        decrypted = _xor_cipher(raw)
        return decrypted.decode("utf-8")
    except Exception:
        return None


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = None
    try:
        conn = get_connection()
        yield conn
    finally:
        if conn:
            release_connection(conn)


def _sanitize_grant_row(row: dict) -> dict:
    """Return a grant row without sensitive token fields."""
    allowed_keys = (
        "id",
        "user_id",
        "grant_id",
        "email",
        "provider",
        "created_at",
        "last_sync_at",
        "expires_at",
        "token_type",
        "scope",
    )
    return {key: row.get(key) for key in allowed_keys if key in row}


def _normalize_provider_fields(row: dict) -> dict:
    folders_raw = row.get('provider_folders')
    if folders_raw:
        if isinstance(folders_raw, str):
            try:
                row['provider_folders'] = json.loads(folders_raw)
            except json.JSONDecodeError:
                row['provider_folders'] = []
        elif isinstance(folders_raw, (list, tuple)):
            row['provider_folders'] = list(folders_raw)
    else:
        row['provider_folders'] = []
    return row


def get_connection():
    """Get a database connection."""
    global _pg_pool, _sqlite_conn
    
    if USE_POSTGRES:
        if _pg_pool is None:
            _pg_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10)
        return _pg_pool.getconn()
    else:
        if _sqlite_conn is None:
            _sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _sqlite_conn.row_factory = sqlite3.Row
        return _sqlite_conn


def release_connection(conn):
    """Release a database connection."""
    global _pg_pool, _sqlite_conn
    
    if USE_POSTGRES:
        _pg_pool.putconn(conn)
    else:
        # SQLite doesn't need explicit connection release
        pass


def init_db():
    """Initialize database schema."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                practice_name TEXT,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Sources table (for CloudMailin and other sources)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                inbound_token TEXT UNIQUE NOT NULL,
                inbound_address TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                sender_domain TEXT NOT NULL,
                subject TEXT NOT NULL,
                snippet TEXT,
                zone TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT NOT NULL,
                jone5_message TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                corrected BOOLEAN DEFAULT FALSE,
                corrected_at TIMESTAMP,
                source_id TEXT,
                source_name TEXT,
                
                -- Nylas integration fields
                grant_id TEXT,
                provider_message_id TEXT,
                thread_id TEXT,
                provider TEXT,
                
                -- Full email content
                raw_body TEXT,
                raw_body_html TEXT,
                raw_headers TEXT,
                
                -- Metadata and attachments
                email_metadata TEXT,
                attachments TEXT,
                has_attachments BOOLEAN DEFAULT FALSE,
                
                -- Status and tracking
                status TEXT DEFAULT 'active',
                read_status BOOLEAN DEFAULT FALSE,
                starred BOOLEAN DEFAULT FALSE,
                important BOOLEAN DEFAULT FALSE,
                
                -- AI processing fields
                summary TEXT,
                recommended_action TEXT,
                action_type TEXT,
                draft_reply TEXT,
                llm_fallback BOOLEAN DEFAULT FALSE,
                
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Corrections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                old_zone TEXT NOT NULL,
                new_zone TEXT NOT NULL,
                sender TEXT NOT NULL,
                corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Rule overrides table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rule_overrides (
                id TEXT PRIMARY KEY,
                sender_key TEXT UNIQUE NOT NULL,
                zone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # CloudMailin messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloudmailin_messages (
                id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'cloudmailin-default-user',
                sender TEXT NOT NULL,
                sender_domain TEXT NOT NULL,
                subject TEXT NOT NULL,
                snippet TEXT,
                zone TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT NOT NULL,
                jone5_message TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                corrected BOOLEAN DEFAULT FALSE,
                source_id TEXT DEFAULT 'cloudmailin',
                source_name TEXT DEFAULT 'CloudMailin'
            )
        ''')
        
        # Nylas grants table (stores connected email accounts via Nylas)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nylas_grants (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                grant_id TEXT NOT NULL,
                email TEXT NOT NULL,
                provider TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_sync_at TIMESTAMP,
                expires_at TEXT,
                token_type TEXT,
                scope TEXT,
                access_token TEXT,
                refresh_token TEXT,
                provider_folders TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        if USE_POSTGRES:
            cursor.execute('ALTER TABLE nylas_grants ADD COLUMN IF NOT EXISTS access_token TEXT')
            cursor.execute('ALTER TABLE nylas_grants ADD COLUMN IF NOT EXISTS refresh_token TEXT')
            cursor.execute('ALTER TABLE nylas_grants ADD COLUMN IF NOT EXISTS expires_at TEXT')
            cursor.execute('ALTER TABLE nylas_grants ADD COLUMN IF NOT EXISTS token_type TEXT')
            cursor.execute('ALTER TABLE nylas_grants ADD COLUMN IF NOT EXISTS scope TEXT')
        else:
            for column in [
                ("access_token", "TEXT"),
                ("refresh_token", "TEXT"),
                ("expires_at", "TEXT"),
                ("token_type", "TEXT"),
                ("scope", "TEXT"),
            ]:
                try:
                    cursor.execute(f'ALTER TABLE nylas_grants ADD COLUMN {column[0]} {column[1]}')
                except Exception:
                    pass
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sources_user_id ON sources(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sources_inbound_token ON sources(inbound_token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nylas_grants_user_id ON nylas_grants(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nylas_grants_grant_id ON nylas_grants(grant_id)')
        
        conn.commit()
        
    finally:
        release_connection(conn)


def create_state_vector_tables():
    """Create state vector tables for AI processing."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Message state vectors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_state_vectors (
                id TEXT PRIMARY KEY,
                nylas_message_id TEXT UNIQUE NOT NULL,
                grant_id TEXT NOT NULL,
                intent_label TEXT NOT NULL,
                risk_score REAL NOT NULL,
                context_blob TEXT DEFAULT '{}',
                summary TEXT,
                current_owner_role TEXT,
                deadline_at TIMESTAMP,
                lifecycle_state TEXT DEFAULT 'NEW',
                is_overdue BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Message events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_events (
                id TEXT PRIMARY KEY,
                vector_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vector_id) REFERENCES message_state_vectors(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vectors_lifecycle ON message_state_vectors(lifecycle_state)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vectors_risk ON message_state_vectors(risk_score DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vectors_deadline ON message_state_vectors(deadline_at)')
        
        conn.commit()
        
    finally:
        release_connection(conn)


# User operations
def create_user(user_data: dict) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (id, email, name, practice_name, hashed_password)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_data["id"],
            user_data["email"],
            user_data["name"],
            user_data.get("practice_name"),
            user_data["hashed_password"]
        ))
        conn.commit()
        return user_data
    finally:
        release_connection(conn)


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        release_connection(conn)


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        release_connection(conn)


# Message operations
def create_message(message_data: dict) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Prepare the insert statement with all the fields
        fields = [
            'id', 'user_id', 'sender', 'sender_domain', 'subject', 'snippet',
            'zone', 'confidence', 'reason', 'jone5_message', 'received_at',
            'classified_at', 'corrected', 'corrected_at', 'source_id', 'source_name',
            'grant_id', 'provider_message_id', 'thread_id', 'provider',
            'raw_body', 'raw_body_html', 'raw_headers', 'email_metadata',
            'attachments', 'has_attachments', 'status', 'read_status',
            'starred', 'important', 'summary', 'recommended_action',
            'action_type', 'draft_reply', 'llm_fallback'
        ]
        
        placeholders = ', '.join(['?' for _ in fields])
        
        cursor.execute(f'''
            INSERT INTO messages ({placeholders})
            VALUES ({placeholders})
        ''', tuple(message_data.get(field) for field in fields))
        
        conn.commit()
        return message_data
    finally:
        release_connection(conn)


def get_message_by_id(message_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE id = ? AND user_id = ?
        ''', (message_id, user_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        release_connection(conn)


def get_messages_by_user(user_id: str, zone: str = None, limit: int = 100) -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        if zone:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE user_id = ? AND zone = ?
                ORDER BY received_at DESC
                LIMIT ?
            ''', (user_id, zone, limit))
        else:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE user_id = ?
                ORDER BY received_at DESC
                LIMIT ?
            ''', (user_id, limit))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        release_connection(conn)


def update_message_full_content(message_id: str, user_id: str, raw_body: str | None, raw_body_html: str | None) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE messages 
            SET raw_body = ?, raw_body_html = ?
            WHERE id = ? AND user_id = ?
        ''', (raw_body, raw_body_html, message_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        release_connection(conn)


# Nylas grant operations
def create_nylas_grant(grant: dict) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        encrypted_access = encrypt_token(grant.get('access_token'))
        encrypted_refresh = encrypt_token(grant.get('refresh_token'))
        scope = grant.get('scope')
        last_sync_at = grant.get('last_sync_at')

        cursor.execute('SELECT id, created_at FROM nylas_grants WHERE grant_id = ?', (grant['grant_id'],))
        existing = cursor.fetchone()

        if existing:
            existing_dict = dict(existing)
            cursor.execute('''
                UPDATE nylas_grants
                SET email = ?, provider = ?, last_sync_at = ?, access_token = ?, refresh_token = ?, expires_at = ?, token_type = ?, scope = ?
                WHERE grant_id = ?
            ''', (
                grant['email'],
                grant.get('provider'),
                last_sync_at,
                encrypted_access,
                encrypted_refresh,
                grant.get('expires_at'),
                grant.get('token_type'),
                scope,
                grant['grant_id']
            ))
            grant_id = grant['grant_id']
        else:
            grant_id = f"grant_{uuid.uuid4().hex}"
            cursor.execute('''
                INSERT INTO nylas_grants (id, user_id, grant_id, email, provider, created_at, last_sync_at, access_token, refresh_token, expires_at, token_type, scope)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                grant_id,
                grant['user_id'],
                grant['grant_id'],
                grant['email'],
                grant.get('provider'),
                grant.get('created_at', datetime.utcnow().isoformat()),
                last_sync_at,
                encrypted_access,
                encrypted_refresh,
                grant.get('expires_at'),
                grant.get('token_type'),
                scope,
            ))

        conn.commit()
        
        # Return sanitized grant data
        sanitized = _sanitize_grant_row({
            'id': grant_id,
            'user_id': grant['user_id'],
            'grant_id': grant['grant_id'],
            'email': grant['email'],
            'provider': grant.get('provider'),
            'created_at': existing_dict.get('created_at') if existing else grant.get('created_at'),
            'last_sync_at': last_sync_at,
            'expires_at': grant.get('expires_at'),
            'token_type': grant.get('token_type'),
            'scope': scope,
        })
        return sanitized

    finally:
        release_connection(conn)


def get_nylas_grants_by_user(user_id: str) -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, grant_id, email, provider, created_at, last_sync_at, expires_at, token_type, scope
            FROM nylas_grants
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        release_connection(conn)
        return [_sanitize_grant_row(dict(row)) for row in rows]
    finally:
        release_connection(conn)


def get_nylas_grant_by_grant_id(grant_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, grant_id, email, provider, created_at, last_sync_at, expires_at, token_type, scope
            FROM nylas_grants
            WHERE grant_id = ?
        ''', (grant_id,))
        row = cursor.fetchone()
        release_connection(conn)
        return _sanitize_grant_row(dict(row)) if row else None
    finally:
        release_connection(conn)


def get_nylas_grant_credentials(grant_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, email, provider, access_token, refresh_token, expires_at, token_type, scope
            FROM nylas_grants
            WHERE grant_id = ?
        ''', (grant_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            # Decrypt tokens
            if data['access_token']:
                data['access_token'] = decrypt_token(data['access_token'])
            if data['refresh_token']:
                data['refresh_token'] = decrypt_token(data['refresh_token'])
            return data
        return None
    finally:
        release_connection(conn)


def get_all_nylas_grant_credentials() -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT grant_id, user_id, email, provider, access_token, refresh_token, expires_at, token_type, scope FROM nylas_grants')
        rows = cursor.fetchall()
        release_connection(conn)
        results = []
        for row in rows:
            data = dict(row)
            if data['access_token']:
                data['access_token'] = decrypt_token(data['access_token'])
            if data['refresh_token']:
                data['refresh_token'] = decrypt_token(data['refresh_token'])
            results.append(data)
        return results
    finally:
        release_connection(conn)


def update_nylas_grant_sync_time(grant_id: str, last_sync_at: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE nylas_grants SET last_sync_at = ? WHERE grant_id = ?', (last_sync_at, grant_id))
        conn.commit()
        release_connection(conn)
    finally:
        release_connection(conn)


def update_nylas_grant_tokens(
    grant_id: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
    expires_at: str | None = None,
    token_type: str | None = None,
    scope: str | None = None,
) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        updates = {}
        if access_token is not None:
            updates['access_token'] = encrypt_token(access_token)
        if refresh_token is not None:
            updates['refresh_token'] = encrypt_token(refresh_token)
        if expires_at is not None:
            updates['expires_at'] = expires_at
        if token_type is not None:
            updates['token_type'] = token_type
        if scope is not None:
            updates['scope'] = scope

        if updates:
            set_clause = ', '.join(f"{column} = ?" for column in updates.keys())
            values = list(updates.values())
            values.append(grant_id)
            cursor.execute(f'UPDATE nylas_grants SET {set_clause} WHERE grant_id = ?', values)
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        return False
    finally:
        release_connection(conn)


def delete_nylas_grant(grant_id: str, user_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM nylas_grants WHERE grant_id = ? AND user_id = ?', (grant_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        release_connection(conn)
        return deleted
    finally:
        release_connection(conn)


# Source operations
def create_source(source_data: dict) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sources (id, user_id, name, inbound_token, inbound_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            source_data["id"],
            source_data["user_id"],
            source_data["name"],
            source_data["inbound_token"],
            source_data["inbound_address"],
            source_data.get("created_at", datetime.utcnow().isoformat())
        ))
        conn.commit()
        return source_data
    finally:
        release_connection(conn)


def get_source_by_token(token: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sources WHERE inbound_token = ?', (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        release_connection(conn)


# CloudMailin operations
def create_cloudmailin_message(message_data: dict) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cloudmailin_messages 
            (id, user_id, sender, sender_domain, subject, snippet, zone, confidence, reason, jone5_message, received_at, classified_at, corrected, source_id, source_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            message_data["id"],
            message_data.get("user_id", "cloudmailin-default-user"),
            message_data["sender"],
            message_data["sender_domain"],
            message_data["subject"],
            message_data["snippet"],
            message_data["zone"],
            message_data["confidence"],
            message_data["reason"],
            message_data["jone5_message"],
            message_data.get("received_at", datetime.utcnow().isoformat()),
            message_data.get("classified_at", datetime.utcnow().isoformat()),
            message_data.get("corrected", False),
            message_data.get("source_id", "cloudmailin"),
            message_data.get("source_name", "CloudMailin")
        ))
        conn.commit()
        return message_data
    finally:
        release_connection(conn)


def get_cloudmailin_messages() -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cloudmailin_messages ORDER BY received_at DESC')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        release_connection(conn)


def update_cloudmailin_message_status(message_id: str, status: str, snoozed_until: str | None = None) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if snoozed_until:
            cursor.execute('''
                UPDATE cloudmailin_messages 
                SET status = ?, snoozed_until = ?
                WHERE id = ?
            ''', (status, snoozed_until, message_id))
        else:
            cursor.execute('''
                UPDATE cloudmailin_messages 
                SET status = ?
                WHERE id = ?
            ''', (status, message_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        release_connection(conn)


def delete_cloudmailin_message(message_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cloudmailin_messages WHERE id = ?', (message_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        release_connection(conn)


def get_nylas_grants_by_email(email: str) -> list:
    """Get grants by email (for linking during registration)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM nylas_grants WHERE email = ?', (email,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting grants by email: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)


def update_nylas_grant_user_id(grant_id: str, user_id: str) -> bool:
    """Update grant user_id (for linking after registration)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE nylas_grants SET user_id = ? WHERE grant_id = ?', (user_id, grant_id))
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"Error updating grant user_id: {e}")
        return False
    finally:
        if conn:
            release_connection(conn)


def update_message_provider_state(
    message_id: str,
    provider_grant_id: str,
    provider_message_id: str,
    provider: str,
    thread_id: str | None = None,
    provider_folders: list | None = None,
    provider_unread: bool = True,
):
    """Update message with Nylas provider information."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE messages 
            SET grant_id = ?, provider_message_id = ?, provider = ?, thread_id = ?, provider_folders = ?, provider_unread = ?
            WHERE id = ?
        ''', (
            provider_grant_id,
            provider_message_id,
            provider,
            thread_id,
            json.dumps(provider_folders) if provider_folders else None,
            provider_unread,
            message_id
        ))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        release_connection(conn)
