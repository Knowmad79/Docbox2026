# Email Verification System - Setup Guide

## ✅ What's Implemented

1. **Database Schema**
   - `users.is_verified` - Boolean flag for verified status
   - `users.verified_at` - Timestamp when verified
   - `email_verifications` table - Stores verification tokens

2. **Registration Flow**
   - Registration returns immediately (no timeout!)
   - Verification email sent in background
   - User must verify email before login

3. **Verification Endpoints**
   - `GET /api/auth/verify-email?token=xxx` - Verify email
   - `POST /api/auth/resend-verification` - Resend verification email

4. **Frontend Updates**
   - Increased timeout for registration (60 seconds)
   - Shows verification message after registration
   - Handles verification success/error from URL

---

## 🔧 Email Sending Integration

Currently, verification emails are **logged to console**. To send actual emails, integrate one of these services:

### Option 1: Nylas (Recommended - You Already Have It)

Since you're using Nylas, set up a system email account:

```python
# In send_verification_email function, replace with:
def send_verification_email(email: str, name: str, verification_token: str):
    if not nylas_client:
        print("Nylas not configured - email not sent")
        return
    
    # Get system email grant (set this up once)
    SYSTEM_GRANT_ID = os.environ.get("SYSTEM_EMAIL_GRANT_ID")
    if not SYSTEM_GRANT_ID:
        print("System email grant not configured")
        return
    
    frontend_url = os.environ.get("FRONTEND_URL", "https://full-stack-apps-ah1tro24.devinapps.com")
    verification_url = f"{frontend_url}/verify-email?token={verification_token}"
    
    try:
        nylas_client.messages.send(
            SYSTEM_GRANT_ID,
            request_body={
                "to": [{"email": email}],
                "subject": "Verify your DocBoxRX account",
                "body": f"""Hi {name},

Please verify your email by clicking this link:
{verification_url}

This link expires in 24 hours.

If you didn't create this account, please ignore this email.

Best regards,
DocBoxRX Team"""
            }
        )
    except Exception as e:
        print(f"Failed to send verification email: {e}")
```

**Setup Steps:**
1. Create a system email account (e.g., `noreply@yourdomain.com` or use your personal email)
2. Connect it via Nylas OAuth
3. Get the grant_id and set `SYSTEM_EMAIL_GRANT_ID` environment variable

### Option 2: SendGrid (Simple & Reliable)

```bash
pip install sendgrid
```

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_verification_email(email: str, name: str, verification_token: str):
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    if not SENDGRID_API_KEY:
        return
    
    frontend_url = os.environ.get("FRONTEND_URL", "https://full-stack-apps-ah1tro24.devinapps.com")
    verification_url = f"{frontend_url}/verify-email?token={verification_token}"
    
    message = Mail(
        from_email='noreply@docboxrx.com',
        to_emails=email,
        subject='Verify your DocBoxRX account',
        html_content=f"""
        <p>Hi {name},</p>
        <p>Please verify your email by clicking this link:</p>
        <p><a href="{verification_url}">{verification_url}</a></p>
        <p>This link expires in 24 hours.</p>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
    except Exception as e:
        print(f"Failed to send email: {e}")
```

### Option 3: AWS SES (Scalable)

```bash
pip install boto3
```

```python
import boto3

def send_verification_email(email: str, name: str, verification_token: str):
    ses_client = boto3.client('ses', region_name='us-east-1')
    
    frontend_url = os.environ.get("FRONTEND_URL", "https://full-stack-apps-ah1tro24.devinapps.com")
    verification_url = f"{frontend_url}/verify-email?token={verification_token}"
    
    try:
        ses_client.send_email(
            Source='noreply@docboxrx.com',
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': 'Verify your DocBoxRX account'},
                'Body': {
                    'Text': {
                        'Data': f"""Hi {name},

Please verify your email by clicking this link:
{verification_url}

This link expires in 24 hours."""
                    }
                }
            }
        )
    except Exception as e:
        print(f"Failed to send email: {e}")
```

### Option 4: SMTP (Simple, Works with Any Provider)

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_verification_email(email: str, name: str, verification_token: str):
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP credentials not configured")
        return
    
    frontend_url = os.environ.get("FRONTEND_URL", "https://full-stack-apps-ah1tro24.devinapps.com")
    verification_url = f"{frontend_url}/verify-email?token={verification_token}"
    
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = email
    msg['Subject'] = "Verify your DocBoxRX account"
    
    body = f"""Hi {name},

Please verify your email by clicking this link:
{verification_url}

This link expires in 24 hours.

If you didn't create this account, please ignore this email."""
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")
```

---

## 🚀 Quick Setup (Recommended: Nylas)

1. **Connect a system email account via Nylas:**
   ```bash
   # Use your existing Nylas setup
   # Connect an email account (can be your personal email for now)
   # Get the grant_id from the nylas_grants table
   ```

2. **Set environment variable:**
   ```bash
   flyctl secrets set SYSTEM_EMAIL_GRANT_ID=your_grant_id_here
   ```

3. **Update `send_verification_email` function** in `main.py` with Nylas code above

4. **Deploy:**
   ```bash
   cd docboxrx-backend
   flyctl deploy
   ```

---

## 📋 Future-Proofing Features

### Already Implemented:
- ✅ Async email sending (no timeouts)
- ✅ Token-based verification (secure)
- ✅ Expiring tokens (24 hours)
- ✅ Database tracking of verification status
- ✅ Resend verification capability

### Recommended Additions:
- [ ] Email templates (HTML + plain text)
- [ ] Multiple verification attempts tracking
- [ ] Rate limiting on resend
- [ ] Email change verification
- [ ] Welcome email after verification
- [ ] Password reset via email

---

## 🧪 Testing

1. **Register a new account** - Should return immediately
2. **Check logs** - Verification URL should be printed
3. **Click verification link** - Should redirect and verify
4. **Try to login** - Should work after verification

---

## 📝 Notes

- **Current State**: Emails are logged to console (for development)
- **Production**: Integrate one of the email services above
- **Security**: Tokens are hashed and expire after 24 hours
- **Scalability**: Background tasks ensure registration never times out
