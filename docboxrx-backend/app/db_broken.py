def encrypt_token(value: str | None) -> str | None:
def decrypt_token(value: str | None) -> str | None:
def _normalize_provider_fields(row: dict) -> dict:
def update_cloudmailin_message_status(message_id: str, status: str, snoozed_until: str | None = None) -> bool:
def delete_cloudmailin_message(message_id: str) -> bool:
def get_nylas_grant_credentials(grant_id: str) -> dict | None:
def get_all_nylas_grant_credentials() -> list:
def update_nylas_grant_tokens(
def update_message_provider_state(
def create_state_vector_tables():
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



