from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.state_vector import MessageStateVector

router = APIRouter(prefix="/api/briefing", tags=["Briefing"])


class MessageStateVectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Any
    nylas_message_id: str
    grant_id: str
    intent_label: str
    risk_score: float
    context_blob: dict
    summary: Optional[str] = None
    current_owner_role: Optional[str] = None
    deadline_at: Optional[datetime] = None
    lifecycle_state: Optional[str] = None
    is_overdue: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("/daily-deck", response_model=list[MessageStateVectorOut])
async def get_daily_deck(role: str = "lead_doctor", db: AsyncSession = Depends(get_db)):
    stmt = (
        select(MessageStateVector)
        .where(
            MessageStateVector.current_owner_role == role,
            MessageStateVector.lifecycle_state.in_(["NEW", "ASSIGNED"]),
        )
        .order_by(MessageStateVector.risk_score.desc(), MessageStateVector.deadline_at.asc())
        .limit(20)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{vector_id}/action")
async def take_action(vector_id: str, action: str, db: AsyncSession = Depends(get_db)):
    return {"status": "success", "action": action, "vector_id": vector_id}
