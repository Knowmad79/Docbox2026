"""
DocBox MVP API Contract (OpenAPI Spec)
This file defines the backend API endpoints for Nylas OAuth, webhooks, message retrieval, Smart Compose, and metadata tagging.
All field names/types match the shared DB schema and frontend contract.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter()

# --- NYLAS OAUTH ---
@router.post("/api/nylas/auth-url")
def get_auth_url(provider: str):
    """
    Request: { provider: "google" | "microsoft" }
    Response: { auth_url: string }
    """
    # TODO: Generate Nylas OAuth URL for the provider
    return {"auth_url": f"https://nylas.com/oauth/{provider}"}

@router.post("/api/nylas/callback")
def nylas_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Request: { code: string, state: string }
    Response: { grant_id: string, email: string }
    """
    # TODO: Exchange code for grant_id/email via Nylas API
    return {"grant_id": "nylas-grant-id", "email": "user@example.com"}

# --- WEBHOOK INGESTION ---
@router.post("/webhooks/messages")
def webhook_messages(request: Request, db: Session = Depends(get_db)):
    """
    Receives Nylas webhook for message.created
    """
    # TODO: Validate signature, parse payload, store message
    return JSONResponse({"ok": True})

# --- MESSAGE RETRIEVAL ---
@router.get("/api/messages")
def get_messages(db: Session = Depends(get_db)):
    """
    Response: { messages: Message[] }
    """
    # TODO: Query messages from DB
    return {"messages": []}

@router.get("/api/messages/{id}")
def get_message(id: str, db: Session = Depends(get_db)):
    """
    Response: Message (full HTML, attachments, thread)
    """
    # TODO: Query message by id
    return {"id": id}

# --- SMART COMPOSE (EXTRACTION & REPLY) ---
@router.post("/api/messages/{id}/extract")
def extract_obligation(id: str, db: Session = Depends(get_db)):
    """
    Extract obligation data from message using Nylas Smart Compose
    """
    # TODO: Call Nylas Smart Compose, store result
    return {"obligation_type": "", "deadline": "", "financial_impact": 0, "required_action": ""}

@router.post("/api/messages/{id}/reply")
def generate_reply(id: str, body: str, db: Session = Depends(get_db)):
    """
    Request: { body: string }
    Response: { sent: boolean, message_id: string }
    """
    # TODO: Call Nylas Smart Compose to generate/send reply
    return {"sent": True, "message_id": id}

# --- METADATA TAGGING ---
@router.put("/api/messages/{id}/metadata")
def update_metadata(id: str, metadata: dict, db: Session = Depends(get_db)):
    """
    Request: { metadata: {...} }
    Response: { updated: boolean }
    """
    # TODO: Update message metadata in DB
    return {"updated": True}

@router.get("/api/messages/metadata")
def filter_by_metadata(key: str, value: str, db: Session = Depends(get_db)):
    """
    Query messages by metadata key/value
    """
    # TODO: Query messages by metadata
    return {"messages": []}
