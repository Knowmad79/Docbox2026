import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.main import process_shadow_traffic


async def test_shadow_worker(grant_id: str, message_id: str, repeat: int = 1):
    print(f"🧪 Testing Shadow Worker (repeat={repeat})")
    print(f"   Grant ID: {grant_id}")
    print(f"   Message ID: {message_id}")
    print("="*60 + "\n")
    
    for i in range(repeat):
        if repeat > 1:
            print(f"--- RUN {i+1}/{repeat} ---")
        await process_shadow_traffic(grant_id, message_id)
        if repeat > 1:
            print("\n" + "="*60)
    print(f"SUCCESS: Test complete! Ran {repeat} time(s)")
    print("="*60)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_shadow_worker.py <grant_id> <message_id> [repeat]")
        print("\nExample:")
        print('  python test_shadow_worker.py "23d325e6-0a82-44a7-9f73-65b9b7dc25be" "19b9f67b80e84fd4"')
        print('  python test_shadow_worker.py "23d325e6-0a82-44a7-9f73-65b9b7dc25be" "19b9f67b80e84fd4" 20')
        sys.exit(1)
    
    grant_id = sys.argv[1]
    message_id = sys.argv[2]
    repeat = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    asyncio.run(test_shadow_worker(grant_id, message_id, repeat))
