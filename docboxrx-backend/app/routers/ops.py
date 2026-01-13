import os
import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.database import async_session, AsyncSession

router = APIRouter(prefix="/ops", tags=["ops"])
START_TIME = time.time()

async def get_db():
    async with async_session() as session:
        yield session

@router.get("/diag")
async def diag(db: AsyncSession = Depends(get_db)):
    # Database check
    db_ok = True
    db_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)

    return {
        "ok": True,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "db_ok": db_ok,
        "db_error": db_error,
        "nylas_configured": bool(
            os.getenv("NYLAS_API_KEY") or os.getenv("NYLAS_CLIENT_ID")
        ),
        "ai_configured": bool(
            os.getenv("CEREBRAS_API_KEY") or os.getenv("AI_API_KEY")
        ),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }
