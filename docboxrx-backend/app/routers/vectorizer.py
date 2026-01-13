import os
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.state_vector import MessageStateVector
from app.services.vectorizer import vectorizer, EmailInput
from app.services.state_machine import StateMachine

router = APIRouter(prefix="/vectorizer", tags=["vectorizer"])

# Webhook endpoint for Nylas events
@router.post("/webhook")
async def handle_nylas_webhook(event: dict, db: AsyncSession = Depends(get_db)):
    """
    Handle Nylas webhook events for new messages.
    This is the "Shadow Router" that processes incoming emails.
    """
    try:
        # Check if this is a message created event
        if event.get("type") == "message.created":
            # Extract relevant data
            data = event.get("object", {})
            message_id = data.get("id")
            grant_id = data.get("grant_id")
            subject = data.get("subject", "")
            sender = data.get("from", [{}])[0].get("email", "") if data.get("from") else ""
            
            # Get the full message content (this would typically be fetched separately)
            # For now, we'll create a basic email input with available data
            email_input = EmailInput(
                subject=subject,
                body="",  # In a real implementation, we'd fetch the full body
                sender=sender,
                message_id=message_id,
                grant_id=grant_id
            )
            
            # Vectorize the email
            vector_data = await vectorizer.vectorize_email(email_input)
            
            # Create a new state vector
            state_vector = MessageStateVector(**vector_data)
            db.add(state_vector)
            await db.commit()
            await db.refresh(state_vector)
            
            # Trigger state machine
            state_machine = StateMachine(db)
            await state_machine.process_new_message(state_vector.id)
            
            return {"status": "success", "vector_id": str(state_vector.id)}
        else:
            return {"status": "ignored", "reason": "Not a message.created event"}
            
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")


@router.post("/vectorize")
async def vectorize_message(email_input: EmailInput, db: AsyncSession = Depends(get_db)):
    """
    Manually vectorize an email message.
    """
    try:
        # Vectorize the email
        vector_data = await vectorizer.vectorize_email(email_input)
        
        # Create a new state vector
        state_vector = MessageStateVector(**vector_data)
        db.add(state_vector)
        await db.commit()
        await db.refresh(state_vector)
        
        # Trigger state machine
        state_machine = StateMachine(db)
        await state_machine.process_new_message(state_vector.id)
        
        return {"status": "success", "vector": vector_data, "vector_id": str(state_vector.id)}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to vectorize message: {str(e)}")


@router.get("/vectors/{vector_id}")
async def get_vector(vector_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get a specific state vector by ID.
    """
    try:
        stmt = select(MessageStateVector).where(MessageStateVector.id == vector_id)
        result = await db.execute(stmt)
        vector = result.scalar_one_or_none()
        
        if not vector:
            raise HTTPException(status_code=404, detail="Vector not found")
            
        return vector
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve vector: {str(e)}")


@router.get("/vectors")
async def list_vectors(
    skip: int = 0, 
    limit: int = 100, 
    lifecycle_state: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List state vectors with optional filtering.
    """
    try:
        stmt = select(MessageStateVector)
        
        if lifecycle_state:
            stmt = stmt.where(MessageStateVector.lifecycle_state == lifecycle_state)
            
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        vectors = result.scalars().all()
        
        return vectors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list vectors: {str(e)}")