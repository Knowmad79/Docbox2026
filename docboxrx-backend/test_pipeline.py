import asyncio
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.services.vectorizer import vectorizer, EmailInput
from app.services.router import router
from app.database import async_session
from app.models.state_vector import MessageStateVector


async def run_dry_run() -> None:
    print("🧪 STARTING DRY RUN: The 'Bleeding Patient' Test")

    fake_email = EmailInput(
        subject="URGENT: Patient John Doe - Post-Op Bleeding",
        body=(
            "Hi Dr. Smith, John Doe (DOB 01/01/80) called. "
            "He is bleeding from the extraction site. Gauze is soaked. "
            "What should we do?"
        ),
        sender="sarah.nurse@gmail.com",
        message_id=f"test_msg_{int(asyncio.get_running_loop().time() * 1000)}",
        grant_id="test_grant_123",
    )

    print(f"\nEMAIL INPUT: {fake_email.subject}")

    print("Step 1: Vectorizing (Calling AI)...")
    vector_data = await vectorizer.vectorize_email(fake_email)
    print(f"   SUCCESS: AI Result: Intent={vector_data['intent_label']} | Risk={vector_data['risk_score']}")

    print("Step 2: Routing...")
    routed_data = router.route_vector(vector_data)
    print(f"   SUCCESS: Routed To: {routed_data.get('current_owner_role')}")

    print("Step 3: Saving to Database...")
    async with async_session() as session:
        db_obj = MessageStateVector(**routed_data)
        session.add(db_obj)
        try:
            await session.commit()
            await session.refresh(db_obj)
            print(f"   SUCCESS! Saved to DB with ID: {db_obj.id}")
            print("SUCCESS: The system is LIVE. This email is now a State Vector.")
        except Exception as e:
            await session.rollback()
            print(f"ERROR: DB Save Failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_dry_run())
