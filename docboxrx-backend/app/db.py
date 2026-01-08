"""Database module for persistent storage using PostgreSQL or SQLite."""
import base64
import json
import os
import uuid
from datetime import datetime, timedelta
import hashlib

# Check if we have a PostgreSQL DATABASE_URL
# Fallback to Neon Postgres if DATABASE_URL is not set in environment
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_Z60uvbwqlBzk@ep-mute-hill-adb7l32q-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require")
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

    if 'provider_unread' in row and row['provider_unread'] is not None:
        row['provider_unread'] = bool(row['provider_unread'])
    if 'llm_fallback' in row and row['llm_fallback'] is not None:
        row['llm_fallback'] = bool(row['llm_fallback'])
    return row

def _get_pg_pool():
    """Get or create the Postgres connection pool with timeout settings."""
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = ConnectionPool(
                DATABASE_URL,
                min_size=1,
                max_size=10,
                max_idle=300,  # Close idle connections after 5 minutes
                max_lifetime=3600,  # Recycle connections after 1 hour
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 5,  # 5 second connection timeout
                }
            )
        except Exception as e:
            print(f"Failed to create connection pool: {e}")
            raise
    return _pg_pool

def get_connection():
    """Get a database connection with timeout handling."""
    global _sqlite_conn
    if USE_POSTGRES:
        try:
            pool = _get_pg_pool()
            # Get connection with timeout
            conn = pool.getconn(timeout=5)  # 5 second timeout
            return conn
        except Exception as e:
            print(f"Failed to get database connection: {e}")
            # Try to recreate pool
            global _pg_pool
            _pg_pool = None
            raise
    else:
        if _sqlite_conn is None:
            _sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=5.0)
            _sqlite_conn.row_factory = sqlite3.Row
        return _sqlite_conn

def release_connection(conn):
    """Release a connection back to the pool (Postgres only)."""
    if USE_POSTGRES and _pg_pool is not None and conn is not None:
        try:
            _pg_pool.putconn(conn)
        except Exception as e:
            print(f"Error releasing connection: {e}")
            # If connection is bad, close it instead
            try:
                conn.close()
            except:
                pass

def p(query):
    """Convert SQLite ? placeholders to PostgreSQL %s placeholders."""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

def init_db():
    """Initialize the database tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            practice_name TEXT,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            verified_at TEXT
        )
    ''')
    
    # Email verification tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_verifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            verified_at TEXT,
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
            received_at TEXT NOT NULL,
            classified_at TEXT NOT NULL,
            corrected INTEGER DEFAULT 0,
            corrected_at TEXT,
            source_id TEXT,
            source_name TEXT,
            summary TEXT,
            recommended_action TEXT,
            action_type TEXT,
            draft_reply TEXT,
            llm_fallback INTEGER DEFAULT 0,
            provider_message_id TEXT,
            provider_thread_id TEXT,
            provider_grant_id TEXT,
            provider_folders TEXT,
            provider_unread INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Add email verification columns to users table
    if USE_POSTGRES:
        cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified INTEGER DEFAULT 0')
        cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS verified_at TEXT')
    else:
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN verified_at TEXT')
        except:
            pass
    
    # Add agent columns if they don't exist (for existing databases)
    # Use PostgreSQL-compatible syntax with IF NOT EXISTS
    if USE_POSTGRES:
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS summary TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS recommended_action TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS action_type TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS draft_reply TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS llm_fallback INTEGER DEFAULT 0')
        # Add workflow state columns for Action Center
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS status TEXT DEFAULT \'active\'')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS snoozed_until TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS needs_reply INTEGER DEFAULT 0')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS replied_at TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider_message_id TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider_thread_id TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider_grant_id TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider_folders TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider_unread INTEGER')
        # Add raw_body for storing full email content
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS raw_body TEXT')
        cursor.execute('ALTER TABLE messages ADD COLUMN IF NOT EXISTS raw_body_html TEXT')
    else:
        # SQLite doesn't support IF NOT EXISTS for columns, use try/except
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN summary TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN recommended_action TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN action_type TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN draft_reply TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN llm_fallback INTEGER DEFAULT 0')
        except:
            pass
        # Add workflow state columns for Action Center
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN status TEXT DEFAULT \'active\'')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN snoozed_until TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN needs_reply INTEGER DEFAULT 0')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN replied_at TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN provider_message_id TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN provider_thread_id TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN provider_grant_id TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN provider_folders TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN provider_unread INTEGER')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN raw_body TEXT')
        except:
            pass
    
    # Sources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            inbound_token TEXT UNIQUE NOT NULL,
            inbound_address TEXT NOT NULL,
            created_at TEXT NOT NULL,
            email_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
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
            corrected_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Rule overrides table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rule_overrides (
            sender_key TEXT PRIMARY KEY,
            zone TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # CloudMailin messages table (for public endpoint)
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
            received_at TEXT NOT NULL,
            classified_at TEXT NOT NULL,
            corrected INTEGER DEFAULT 0,
            source_id TEXT DEFAULT 'cloudmailin',
            source_name TEXT DEFAULT 'CloudMailin',
            raw_headers TEXT,
            raw_body TEXT,
            llm_fallback INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            snoozed_until TEXT
        )
    ''')

    if USE_POSTGRES:
        cursor.execute('ALTER TABLE cloudmailin_messages ADD COLUMN IF NOT EXISTS raw_headers TEXT')
        cursor.execute('ALTER TABLE cloudmailin_messages ADD COLUMN IF NOT EXISTS raw_body TEXT')
        cursor.execute('ALTER TABLE cloudmailin_messages ADD COLUMN IF NOT EXISTS llm_fallback INTEGER DEFAULT 0')
        cursor.execute('ALTER TABLE cloudmailin_messages ADD COLUMN IF NOT EXISTS status TEXT DEFAULT \'active\'')
        cursor.execute('ALTER TABLE cloudmailin_messages ADD COLUMN IF NOT EXISTS snoozed_until TEXT')
    else:
        for column in [
            ("raw_headers", "TEXT"),
            ("raw_body", "TEXT"),
            ("llm_fallback", "INTEGER"),
            ("status", "TEXT"),
            ("snoozed_until", "TEXT"),
        ]:
            try:
                cursor.execute(f'ALTER TABLE cloudmailin_messages ADD COLUMN {column[0]} {column[1]}')
            except Exception:
                pass
    
    # Nylas grants table (stores connected email accounts via Nylas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nylas_grants (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            grant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            provider TEXT,
            created_at TEXT NOT NULL,
            last_sync_at TEXT,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TEXT,
            token_type TEXT,
            scope TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sources_user_id ON sources(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sources_inbound_token ON sources(inbound_token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nylas_grants_user_id ON nylas_grants(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nylas_grants_grant_id ON nylas_grants(grant_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_verifications_token ON email_verifications(token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_verifications_user_id ON email_verifications(user_id)')
    
    conn.commit()
    release_connection(conn)
    if USE_POSTGRES:
        print("PostgreSQL database initialized")
    else:
        print(f"SQLite database initialized at {DB_PATH}")

# User operations
def create_user(user_id: str, email: str, name: str, practice_name: str, hashed_password: str, is_verified: bool = False) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    cursor.execute(
        p('INSERT INTO users (id, email, name, practice_name, hashed_password, created_at, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?)'),
        (user_id, email, name, practice_name, hashed_password, created_at, 1 if is_verified else 0)
    )
    conn.commit()
    release_connection(conn)
    return {"id": user_id, "email": email, "name": name, "practice_name": practice_name, "hashed_password": hashed_password, "created_at": created_at, "is_verified": is_verified}

def create_email_verification(user_id: str, email: str, token: str, expires_in_hours: int = 24) -> dict:
    """Create an email verification token."""
    conn = get_connection()
    cursor = conn.cursor()
    verification_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    expires_at = (datetime.utcnow() + timedelta(hours=expires_in_hours)).isoformat()
    cursor.execute(
        p('INSERT INTO email_verifications (id, user_id, token, email, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)'),
        (verification_id, user_id, token, email, created_at, expires_at)
    )
    conn.commit()
    release_connection(conn)
    return {"id": verification_id, "user_id": user_id, "token": token, "email": email, "created_at": created_at, "expires_at": expires_at}

def get_email_verification(token: str) -> dict | None:
    """Get email verification by token."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('SELECT * FROM email_verifications WHERE token = ? AND verified_at IS NULL AND expires_at > ?'), (token, datetime.utcnow().isoformat()))
    row = cursor.fetchone()
    release_connection(conn)
    return dict(row) if row else None

def verify_email(user_id: str, token: str) -> bool:
    """Mark email as verified."""
    conn = get_connection()
    cursor = conn.cursor()
    verified_at = datetime.utcnow().isoformat()
    # Update verification record
    cursor.execute(p('UPDATE email_verifications SET verified_at = ? WHERE token = ? AND user_id = ?'), (verified_at, token, user_id))
    # Update user record
    cursor.execute(p('UPDATE users SET is_verified = 1, verified_at = ? WHERE id = ?'), (verified_at, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return updated

def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID with proper connection handling."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(p('SELECT * FROM users WHERE id = ?'), (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_user_by_email(email: str) -> dict | None:
    """Get user by email with proper connection handling."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(p('SELECT * FROM users WHERE email = ?'), (email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def email_exists(email: str) -> bool:
    """Check if email exists - optimized for speed."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(p('SELECT 1 FROM users WHERE email = ? LIMIT 1'), (email,))
        row = cursor.fetchone()
        return row is not None
    except Exception as e:
        print(f"Error checking email existence: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

# Message operations
def create_message(message: dict) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        INSERT INTO messages (
            id, user_id, sender, sender_domain, subject, snippet, zone, confidence, reason, jone5_message,
            received_at, classified_at, corrected, source_id, source_name, summary, recommended_action,
            action_type, draft_reply, llm_fallback, provider_message_id, provider_thread_id, provider_grant_id,
            provider_folders, provider_unread, raw_body, raw_body_html
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''), (
        message['id'], message['user_id'], message['sender'], message['sender_domain'],
        message['subject'], message.get('snippet'), message['zone'], message['confidence'],
        message['reason'], message['jone5_message'], message['received_at'], message['classified_at'],
        int(message.get('corrected', False)), message.get('source_id'), message.get('source_name'),
        message.get('summary'), message.get('recommended_action'), message.get('action_type'), message.get('draft_reply'),
        int(message.get('llm_fallback', False)),
        message.get('provider_message_id'), message.get('provider_thread_id'), message.get('provider_grant_id'),
        json.dumps(message.get('provider_folders')) if message.get('provider_folders') is not None else None,
        int(message['provider_unread']) if message.get('provider_unread') is not None else None,
        message.get('raw_body'), message.get('raw_body_html')
    ))
    conn.commit()
    release_connection(conn)
    return _normalize_provider_fields(message.copy())

def get_messages_by_user(user_id: str, zone: str = None) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    if zone:
        cursor.execute(p('SELECT * FROM messages WHERE user_id = ? AND zone = ? ORDER BY received_at DESC'), (user_id, zone))
    else:
        cursor.execute(p('SELECT * FROM messages WHERE user_id = ? ORDER BY received_at DESC'), (user_id,))
    rows = cursor.fetchall()
    release_connection(conn)
    return [_normalize_provider_fields(dict(row)) for row in rows]

def get_message_by_id(message_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('SELECT * FROM messages WHERE id = ? AND user_id = ?'), (message_id, user_id))
    row = cursor.fetchone()
    release_connection(conn)
    return _normalize_provider_fields(dict(row)) if row else None

def update_message_zone(message_id: str, new_zone: str, corrected_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('UPDATE messages SET zone = ?, corrected = 1, corrected_at = ? WHERE id = ?'), (new_zone, corrected_at, message_id))
    conn.commit()
    release_connection(conn)

def delete_message(message_id: str, user_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('DELETE FROM messages WHERE id = ? AND user_id = ?'), (message_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return deleted

# Source operations
def create_source(source: dict) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        INSERT INTO sources (id, user_id, name, inbound_token, inbound_address, created_at, email_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    '''), (
        source['id'], source['user_id'], source['name'], source['inbound_token'],
        source['inbound_address'], source['created_at'], source.get('email_count', 0)
    ))
    conn.commit()
    release_connection(conn)
    return source

def get_sources_by_user(user_id: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('SELECT * FROM sources WHERE user_id = ? ORDER BY created_at DESC'), (user_id,))
    rows = cursor.fetchall()
    release_connection(conn)
    return [dict(row) for row in rows]

def get_source_by_token(inbound_token: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('SELECT * FROM sources WHERE inbound_token = ?'), (inbound_token,))
    row = cursor.fetchone()
    release_connection(conn)
    return dict(row) if row else None

def delete_source(source_id: str, user_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('DELETE FROM sources WHERE id = ? AND user_id = ?'), (source_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return deleted

def increment_source_email_count(source_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('UPDATE sources SET email_count = email_count + 1 WHERE id = ?'), (source_id,))
    conn.commit()
    release_connection(conn)

# Correction operations
def create_correction(correction: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        INSERT INTO corrections (id, user_id, old_zone, new_zone, sender, corrected_at)
        VALUES (?, ?, ?, ?, ?, ?)
    '''), (
        correction['id'], correction['user_id'], correction['old_zone'],
        correction['new_zone'], correction['sender'], correction['corrected_at']
    ))
    conn.commit()
    release_connection(conn)

def get_corrections_by_user(user_id: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('SELECT * FROM corrections WHERE user_id = ? ORDER BY corrected_at DESC'), (user_id,))
    rows = cursor.fetchall()
    release_connection(conn)
    return [dict(row) for row in rows]

# Rule override operations
def set_rule_override(sender_key: str, zone: str):
    conn = get_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute('''
            INSERT INTO rule_overrides (sender_key, zone, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (sender_key) DO UPDATE SET zone = EXCLUDED.zone, created_at = EXCLUDED.created_at
        ''', (sender_key, zone, datetime.utcnow().isoformat()))
    else:
        cursor.execute('''
            INSERT OR REPLACE INTO rule_overrides (sender_key, zone, created_at)
            VALUES (?, ?, ?)
        ''', (sender_key, zone, datetime.utcnow().isoformat()))
    conn.commit()
    release_connection(conn)

def get_rule_override(sender_key: str) -> str | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('SELECT zone FROM rule_overrides WHERE sender_key = ?'), (sender_key,))
    row = cursor.fetchone()
    release_connection(conn)
    if row:
        return row['zone'] if isinstance(row, dict) else row[0]
    return None

# CloudMailin message operations
def create_cloudmailin_message(message: dict) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        INSERT INTO cloudmailin_messages (id, user_id, sender, sender_domain, subject, snippet, zone, confidence, reason, jone5_message, received_at, classified_at, corrected, source_id, source_name, raw_headers, raw_body, llm_fallback, status, snoozed_until)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''), (
        message['id'], message.get('user_id', 'cloudmailin-default-user'), message['sender'], message['sender_domain'],
        message['subject'], message.get('snippet'), message['zone'], message['confidence'],
        message['reason'], message['jone5_message'], message['received_at'], message['classified_at'],
        int(message.get('corrected', False)), message.get('source_id', 'cloudmailin'), message.get('source_name', 'CloudMailin'),
        message.get('raw_headers'), message.get('raw_body'), int(message.get('llm_fallback', False)), message.get('status', 'active'), message.get('snoozed_until')
    ))
    conn.commit()
    release_connection(conn)
    # Normalize booleans and return stored message
    result = dict(message)
    result['llm_fallback'] = bool(result.get('llm_fallback'))
    return result

def get_cloudmailin_messages() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cloudmailin_messages ORDER BY received_at DESC')
    rows = cursor.fetchall()
    release_connection(conn)
    results = []
    for row in rows:
        r = dict(row)
        if 'llm_fallback' in r and r['llm_fallback'] is not None:
            r['llm_fallback'] = bool(r['llm_fallback'])
        results.append(r)
    return results


def update_cloudmailin_message_status(message_id: str, status: str, snoozed_until: str | None = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    if snoozed_until:
        cursor.execute(p('UPDATE cloudmailin_messages SET status = ?, snoozed_until = ? WHERE id = ?'), (status, snoozed_until, message_id))
    else:
        cursor.execute(p('UPDATE cloudmailin_messages SET status = ?, snoozed_until = NULL WHERE id = ?'), (status, message_id))
    updated = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return updated


def delete_cloudmailin_message(message_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('DELETE FROM cloudmailin_messages WHERE id = ?'), (message_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return deleted

# Nylas grant operations
def create_nylas_grant(grant: dict) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    encrypted_access = encrypt_token(grant.get('access_token'))
    encrypted_refresh = encrypt_token(grant.get('refresh_token'))
    expires_at = grant.get('expires_at')
    token_type = grant.get('token_type')
    scope = grant.get('scope')
    last_sync_at = grant.get('last_sync_at')

    cursor.execute(p('SELECT id, created_at FROM nylas_grants WHERE grant_id = ?'), (grant['grant_id'],))
    existing = cursor.fetchone()

    if existing:
        existing_dict = dict(existing)
        cursor.execute(p('''
            UPDATE nylas_grants
            SET email = ?, provider = ?, last_sync_at = ?, access_token = ?, refresh_token = ?, expires_at = ?, token_type = ?, scope = ?
            WHERE grant_id = ?
        '''), (
            grant['email'],
            grant.get('provider'),
            last_sync_at,
            encrypted_access,
            encrypted_refresh,
            expires_at,
            token_type,
            scope,
            grant['grant_id'],
        ))
        conn.commit()
        release_connection(conn)
        sanitized = {
            "id": existing_dict.get('id'),
            "user_id": grant['user_id'],
            "grant_id": grant['grant_id'],
            "email": grant['email'],
            "provider": grant.get('provider'),
            "created_at": existing_dict.get('created_at'),
            "last_sync_at": last_sync_at,
            "expires_at": expires_at,
            "token_type": token_type,
            "scope": scope,
        }
        return sanitized

    cursor.execute(p('''
        INSERT INTO nylas_grants (id, user_id, grant_id, email, provider, created_at, last_sync_at, access_token, refresh_token, expires_at, token_type, scope)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''), (
        grant['id'],
        grant['user_id'],
        grant['grant_id'],
        grant['email'],
        grant.get('provider'),
        grant['created_at'],
        last_sync_at,
        encrypted_access,
        encrypted_refresh,
        expires_at,
        token_type,
        scope,
    ))
    conn.commit()
    release_connection(conn)
    return {
        "id": grant['id'],
        "user_id": grant['user_id'],
        "grant_id": grant['grant_id'],
        "email": grant['email'],
        "provider": grant.get('provider'),
        "created_at": grant['created_at'],
        "last_sync_at": last_sync_at,
        "expires_at": expires_at,
        "token_type": token_type,
        "scope": scope,
    }

def get_nylas_grants_by_user(user_id: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        SELECT id, user_id, grant_id, email, provider, created_at, last_sync_at, expires_at, token_type, scope
        FROM nylas_grants
        WHERE user_id = ?
        ORDER BY created_at DESC
    '''), (user_id,))
    rows = cursor.fetchall()
    release_connection(conn)
    return [_sanitize_grant_row(dict(row)) for row in rows]

def get_nylas_grant_by_grant_id(grant_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        SELECT id, user_id, grant_id, email, provider, created_at, last_sync_at, expires_at, token_type, scope
        FROM nylas_grants
        WHERE grant_id = ?
    '''), (grant_id,))
    row = cursor.fetchone()
    release_connection(conn)
    return _sanitize_grant_row(dict(row)) if row else None


def get_nylas_grant_credentials(grant_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('''
        SELECT user_id, email, provider, access_token, refresh_token, expires_at, token_type, scope
        FROM nylas_grants
        WHERE grant_id = ?
    '''), (grant_id,))
    row = cursor.fetchone()
    release_connection(conn)
    if not row:
        return None
    data = dict(row)
    data['grant_id'] = grant_id
    data['access_token'] = decrypt_token(data.get('access_token'))
    data['refresh_token'] = decrypt_token(data.get('refresh_token'))
    return data


def get_all_nylas_grant_credentials() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT grant_id, user_id, email, provider, access_token, refresh_token, expires_at, token_type, scope FROM nylas_grants')
    rows = cursor.fetchall()
    release_connection(conn)
    results = []
    for row in rows:
        data = dict(row)
        data['access_token'] = decrypt_token(data.get('access_token'))
        data['refresh_token'] = decrypt_token(data.get('refresh_token'))
        results.append(data)
    return results

def update_nylas_grant_sync_time(grant_id: str, last_sync_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('UPDATE nylas_grants SET last_sync_at = ? WHERE grant_id = ?'), (last_sync_at, grant_id))
    conn.commit()
    release_connection(conn)


def update_nylas_grant_tokens(
    grant_id: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
    expires_at: str | None = None,
    scope: str | None = None,
    token_type: str | None = None,
):
    updates = {}
    if access_token is not None:
        updates['access_token'] = encrypt_token(access_token)
    if refresh_token is not None:
        updates['refresh_token'] = encrypt_token(refresh_token)
    if expires_at is not None:
        updates['expires_at'] = expires_at
    if scope is not None:
        updates['scope'] = scope
    if token_type is not None:
        updates['token_type'] = token_type

    if not updates:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ', '.join(f"{column} = ?" for column in updates.keys())
    values = list(updates.values())
    values.append(grant_id)
    cursor.execute(p(f'UPDATE nylas_grants SET {set_clause} WHERE grant_id = ?'), values)
    updated = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return updated

def delete_nylas_grant(grant_id: str, user_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('DELETE FROM nylas_grants WHERE grant_id = ? AND user_id = ?'), (grant_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return deleted

# Message status operations for Action Center
def update_message_status(message_id: str, user_id: str, status: str, snoozed_until: str = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    if snoozed_until:
        cursor.execute(p('UPDATE messages SET status = ?, snoozed_until = ? WHERE id = ? AND user_id = ?'), (status, snoozed_until, message_id, user_id))
    else:
        cursor.execute(p('UPDATE messages SET status = ?, snoozed_until = NULL WHERE id = ? AND user_id = ?'), (status, message_id, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return updated


def update_message_provider_state(
    message_id: str,
    user_id: str,
    provider_unread: bool | None = None,
    provider_folders: list | None = None,
) -> bool:
    updates = {}
    if provider_unread is not None:
        updates['provider_unread'] = int(provider_unread)
    if provider_folders is not None:
        updates['provider_folders'] = json.dumps(provider_folders)

    if not updates:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ', '.join(f"{column} = ?" for column in updates.keys())
    values = list(updates.values())
    values.extend([message_id, user_id])
    cursor.execute(p(f'UPDATE messages SET {set_clause} WHERE id = ? AND user_id = ?'), values)
    updated = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return updated

def mark_message_replied(message_id: str, user_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(p('UPDATE messages SET needs_reply = 0, replied_at = ? WHERE id = ? AND user_id = ?'), (datetime.utcnow().isoformat(), message_id, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    release_connection(conn)
    return updated

def get_nylas_grants_by_email(email: str) -> list:
    """Get grants by email (for linking during registration)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(p('SELECT * FROM nylas_grants WHERE email = ?'), (email,))
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
        cursor.execute(p('UPDATE nylas_grants SET user_id = ? WHERE grant_id = ?'), (user_id, grant_id))
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"Error updating grant user_id: {e}")
        return False
    finally:
        if conn:
            release_connection(conn)

def update_message_full_content(message_id: str, user_id: str, raw_body: str = None, raw_body_html: str = None) -> bool:
    """Update message with full content (jukebox caching)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updates = []
        values = []
        if raw_body is not None:
            updates.append('raw_body = ?')
            values.append(raw_body)
        if raw_body_html is not None:
            updates.append('raw_body_html = ?')
            values.append(raw_body_html)
        if not updates:
            return False
        values.extend([message_id, user_id])
        cursor.execute(p(f'UPDATE messages SET {", ".join(updates)} WHERE id = ? AND user_id = ?'), values)
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"Error updating message full content: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_action_items(user_id: str) -> dict:
    """Get action items for the Action Center / Daily Brief."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    # Get active messages that need action (STAT and TODAY zones, not done/archived)
    cursor.execute(p('''
        SELECT * FROM messages 
        WHERE user_id = ? AND (status IS NULL OR status = 'active') 
        AND zone IN ('STAT', 'TODAY')
        ORDER BY 
            CASE zone WHEN 'STAT' THEN 1 WHEN 'TODAY' THEN 2 ELSE 3 END,
            received_at DESC
    '''), (user_id,))
    urgent_items = [dict(row) for row in cursor.fetchall()]
    
    # Get messages needing reply (action_type = 'reply' and not replied)
    cursor.execute(p('''
        SELECT * FROM messages 
        WHERE user_id = ? AND (status IS NULL OR status = 'active')
        AND action_type = 'reply' AND (replied_at IS NULL)
        ORDER BY received_at DESC
    '''), (user_id,))
    needs_reply = [dict(row) for row in cursor.fetchall()]
    
    # Get snoozed messages that are now due
    cursor.execute(p('''
        SELECT * FROM messages 
        WHERE user_id = ? AND status = 'snoozed' AND snoozed_until <= ?
        ORDER BY snoozed_until ASC
    '''), (user_id, now))
    snoozed_due = [dict(row) for row in cursor.fetchall()]
    
    # Get recently completed items (last 24 hours)
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    cursor.execute(p('''
        SELECT COUNT(*) as count FROM messages 
        WHERE user_id = ? AND status = 'done' AND classified_at >= ?
    '''), (user_id, yesterday))
    done_today = cursor.fetchone()
    done_count = done_today['count'] if isinstance(done_today, dict) else done_today[0]
    
    release_connection(conn)
    
    return {
        'urgent_items': urgent_items,
        'needs_reply': needs_reply,
        'snoozed_due': snoozed_due,
        'done_today': done_count,
        'total_action_items': len(urgent_items) + len(snoozed_due)
    }

# Initialize database on import
init_db()

init_db()
