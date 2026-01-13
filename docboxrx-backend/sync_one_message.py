import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from app import db
from nylas import Client as NylasClient

NYLAS_API_KEY = os.getenv("NYLAS_API_KEY")
NYLAS_API_URI = os.getenv("NYLAS_API_URI", "https://api.us.nylas.com")

nylas_client = NylasClient(api_key=NYLAS_API_KEY, api_uri=NYLAS_API_URI) if NYLAS_API_KEY else None


def sync_one_message():
    print("Syncing one message from Nylas...\n")
    
    if not nylas_client:
        print("ERROR: Nylas client not configured")
        return None, None
    
    grants = db.get_all_nylas_grant_credentials()
    if not grants:
        print("ERROR: No Nylas grants found")
        return None, None
    
    grant_id = grants[0].get('grant_id')
    email = grants[0].get('email')
    
    print(f"Fetching from: {email}")
    print(f"   Grant ID: {grant_id}\n")
    
    try:
        messages_response = nylas_client.messages.list(
            grant_id,
            query_params={"limit": 1, "in": ["INBOX"]}
        )
        
        if not messages_response.data or len(messages_response.data) == 0:
            print("ERROR: No messages found in inbox")
            return None, None
        
        msg = messages_response.data[0]
        
        # Extract message ID
        message_id = getattr(msg, 'id', None) or (msg.get('id') if isinstance(msg, dict) else None)
        subject = getattr(msg, 'subject', None) or (msg.get('subject') if isinstance(msg, dict) else None) or "No Subject"
        
        print(f"SUCCESS: Found message:")
        print(f"   Subject: {subject[:60]}")
        print(f"   Message ID: {message_id}")
        print(f"   Grant ID: {grant_id}")
        
        print("\n" + "="*60)
        print("EXTRACTED IDS FOR TESTING:")
        print("="*60)
        print(f"Grant ID:    {grant_id}")
        print(f"Message ID:  {message_id}")
        print("="*60)
        
        return grant_id, message_id
        
    except Exception as e:
        print(f"ERROR: Failed to fetch message: {e}")
        return None, None


if __name__ == "__main__":
    grant_id, message_id = sync_one_message()
    
    if grant_id and message_id:
        print("\nSUCCESS: Ready to test Shadow Worker!")
        print("\nTest once:")
        print(f'   python test_shadow_worker.py "{grant_id}" "{message_id}"')
        print("\nTest 20 times:")
        print(f'   python test_shadow_worker.py "{grant_id}" "{message_id}" 20')
    else:
        print("\nERROR: Could not extract IDs")
