import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from app import db

def extract_nylas_ids():
    print("Searching for Nylas grant and message IDs...\n")
    
    # 1. Get all Nylas grants
    grants = db.get_all_nylas_grant_credentials()
    
    if not grants:
        print("ERROR: No Nylas grants found in database.")
        print("   You need to connect an email account via Nylas first.")
        return None, None
    
    print(f"SUCCESS: Found {len(grants)} Nylas grant(s):")
    for i, grant in enumerate(grants, 1):
        print(f"   {i}. Grant ID: {grant.get('grant_id')}")
        print(f"      Email: {grant.get('email')}")
        print(f"      Provider: {grant.get('provider')}")
        print()
    
    # Use the first grant
    grant_id = grants[0].get('grant_id')
    
    # 2. Find a message that has provider_grant_id and provider_message_id
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        
        # Query for messages with Nylas provider IDs
        query = db.p("""
            SELECT id, subject, sender, provider_grant_id, provider_message_id 
            FROM messages 
            WHERE provider_grant_id IS NOT NULL 
            AND provider_message_id IS NOT NULL 
            ORDER BY received_at DESC 
            LIMIT 5
        """)
        
        cursor.execute(query)
        messages = cursor.fetchall()
        
        if not messages:
            print("ERROR: No messages found with Nylas provider IDs.")
            print("   Try syncing emails first: POST /api/nylas/sync/{grant_id}")
            return grant_id, None
        
        print(f"SUCCESS: Found {len(messages)} message(s) with Nylas IDs:")
        for i, msg in enumerate(messages, 1):
            msg_dict = dict(msg) if hasattr(msg, 'keys') else {
                'id': msg[0],
                'provider_grant_id': msg[1],
                'provider_message_id': msg[2],
                'subject': msg[3]
            }
            
            message_id = msg_dict['provider_message_id']
            
            print(f"   {i}. Message ID: {message_id}")
            print(f"      Subject: {msg_dict.get('subject', 'No Subject')[:50]}")
        
        # Use the first message
        message_id = messages[0][2]  # provider_message_id is at index 2
        
        print("\n" + "="*60)
        print("EXTRACTED IDS FOR TESTING:")
        print("="*60)
        print(f"Grant ID:    {grant_id}")
        print(f"Message ID:  {message_id}")
        print("="*60)
        
        return grant_id, message_id
        
    finally:
        db.release_connection(conn)


if __name__ == "__main__":
    grant_id, message_id = extract_nylas_ids()
    
    if grant_id and message_id:
        print("\nSUCCESS: Ready to test!")
        print("\nRun this command to test Shadow Worker once:")
        print(f'   python test_shadow_worker.py "{grant_id}" "{message_id}"')
        print("\nOr test 20 times:")
        print(f'   python test_shadow_worker.py "{grant_id}" "{message_id}" 20')
    else:
        print("\nERROR: Could not extract IDs. Please sync emails first.")
