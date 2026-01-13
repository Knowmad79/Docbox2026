from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.state_vector import MessageStateVector, MessageEvent


class StateMachine:
    ALLOWED_TRANSITIONS = {
        "NEW": ["ASSIGNED", "RESOLVED", "ARCHIVED"],
        "ASSIGNED": ["RESOLVED", "ESCALATED", "ARCHIVED"],
        "ESCALATED": ["RESOLVED", "ARCHIVED"],
        "RESOLVED": ["ARCHIVED", "NEW"],
        "ARCHIVED": ["NEW"],
    }

    async def transition(self, db: AsyncSession, vector_id: str, new_state: str, user_id: str = "system") -> MessageStateVector:
        result = await db.execute(select(MessageStateVector).where(MessageStateVector.id == vector_id))
        vector = result.scalar_one_or_none()

        if not vector:
            raise ValueError("Vector not found")

        current_state = vector.lifecycle_state

        if new_state not in self.ALLOWED_TRANSITIONS.get(current_state, []):
            raise ValueError(f"Invalid transition: {current_state} -> {new_state}")

        vector.lifecycle_state = new_state
        vector.updated_at = datetime.now()

        event = MessageEvent(
            vector_id=vector.id,
            event_type="STATE_CHANGE",
            description=f"Changed from {current_state} to {new_state} by {user_id}",
        )
        db.add(event)
        await db.commit()
        await db.refresh(vector)

        return vector


state_machine = StateMachine()
