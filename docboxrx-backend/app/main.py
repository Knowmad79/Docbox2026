from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, BackgroundTasks, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal, List
from datetime import datetime, timedelta
import jwt
import bcrypt
import uuid
import re
import random
import os
import json
import hashlib
import threading
import email
from email import policy
from email.parser import BytesParser
from cerebras.cloud.sdk import Cerebras
from nylas import Client as NylasClient
import asyncio
from sqlalchemy.exc import IntegrityError

# Import database module
from app import db
from app.routers.briefing import router as briefing_router
from app.routers.ops import router as ops_router
from app.routers.api_contract import router as api_contract_router
from app.services.vectorizer import vectorizer, EmailInput
from app.services.router import router as pony_express
from app.models.state_vector import MessageStateVector
from app.database import async_session

# Nylas configuration
NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
if not NYLAS_API_KEY:
    raise ValueError("NYLAS_API_KEY environment variable is required")

NYLAS_CLIENT_ID = os.environ.get("NYLAS_CLIENT_ID")
if not NYLAS_CLIENT_ID:
    raise ValueError("NYLAS_CLIENT_ID environment variable is required")

NYLAS_API_URI = os.environ.get("NYLAS_API_URI", "https://api.us.nylas.com")
NYLAS_CALLBACK_URI = os.environ.get("NYLAS_CALLBACK_URI", "https://app.docboxrx.com/api/nylas/callback")

nylas_client = NylasClient(api_key=NYLAS_API_KEY, api_uri=NYLAS_API_URI) if NYLAS_API_KEY else None

NYLAS_REFRESH_HEADROOM = timedelta(minutes=5)
nylas_grant_cache: dict[str, dict] = {}
nylas_grant_cache_lock = threading.Lock()

# Cerebras API for LLM fallback
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY) if CEREBRAS_API_KEY else None
LLM_CONFIDENCE_THRESHOLD = 0.70  # Use LLM if rules confidence is below this

app = FastAPI(title="DocBoxRX API", description="Sovereign Email Triage System")

# Better error handling for validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        errors.append(f"{field}: {msg}")
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(errors) if errors else "Validation error", "errors": exc.errors()}
    )

# CORS configuration - allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(briefing_router)
app.include_router(ops_router)
app.include_router(api_contract_router)


@app.on_event("startup")
async def initialize_system() -> None:
    """Initialize database and preload Nylas grants at startup."""
    # Initialize database schema (idempotent)
    db.init_db()
    db.create_state_vector_tables()

    # Preload Nylas grants if client is available
    if not nylas_client:
        return
    for grant in db.get_all_nylas_grant_credentials():
        _cache_nylas_grant(grant)


async def process_shadow_traffic(grant_id: str, message_id: str) -> None:
    print(f"Shadow Worker: Waking up for message {message_id}...")

    if not nylas_client:
        print("ERROR: Shadow Worker Failed: Nylas not configured")
        return

    try:
        nylas_message = await asyncio.to_thread(nylas_client.messages.find, grant_id, message_id)

        subject = getattr(nylas_message, 'subject', None) or (nylas_message.get('subject') if isinstance(nylas_message, dict) else None) or "No Subject"
        body_raw = getattr(nylas_message, 'body', None) or (nylas_message.get('body') if isinstance(nylas_message, dict) else None)
        body_html = getattr(nylas_message, 'body_html', None) or (nylas_message.get('body_html') if isinstance(nylas_message, dict) else None)
        body_content = body_html or body_raw or "No Body"

        sender = "unknown"
        from_value = getattr(nylas_message, 'from_', None) or (nylas_message.get('from') if isinstance(nylas_message, dict) else None)
        if from_value and isinstance(from_value, (list, tuple)):
            first = from_value[0]
            if isinstance(first, dict):
                sender = first.get('email') or first.get('name') or sender
            else:
                sender = getattr(first, 'email', None) or getattr(first, 'name', None) or sender

        email_input = EmailInput(
            subject=subject,
            body=body_content,
            sender=sender,
            message_id=message_id,
            grant_id=grant_id,
        )

        print(f"Vectorizing: {email_input.subject[:30]}...")
        vector_data = await vectorizer.vectorize_email(email_input)
        routed_data = pony_express.route_vector(vector_data)

        async with async_session() as session:
            db_obj = MessageStateVector(**routed_data)
            session.add(db_obj)
            try:
                await session.commit()
                await session.refresh(db_obj)
                print(f"SUCCESS: Shadow Success! Saved Vector ID: {db_obj.id} | Risk: {db_obj.risk_score}")
            except IntegrityError:
                await session.rollback()
                print(f"WARNING: Shadow Duplicate: Vector already exists for Nylas message {message_id}")
            except Exception as e:
                await session.rollback()
                print(f"ERROR: DB Save Failed: {e}")

    except Exception as e:
        print(f"ERROR: Shadow Worker Failed: {e}")

# Security
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Health check endpoints
@app.get("/")
async def root():
    return {"status": "ok", "message": "DocBoxRX API is running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "DocBoxRX API", "timestamp": datetime.utcnow().isoformat()}

security = HTTPBearer()

ZoneType = Literal["STAT", "TODAY", "THIS_WEEK", "LATER"]

class EmailSource(BaseModel):
    id: str
    name: str  # e.g., "Gmail Personal", "Work Outlook"
    inbound_token: str  # unique token for this source
    inbound_address: str  # full inbound email address
    created_at: str
    email_count: int = 0

class SourceCreate(BaseModel):
    name: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    practice_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict
    message: Optional[str] = None
    requires_verification: Optional[bool] = None

class EmailIngest(BaseModel):
    sender: str
    sender_domain: Optional[str] = None
    subject: str
    snippet: Optional[str] = None
    source_id: Optional[str] = None  # Which source this email came from

class MessageResponse(BaseModel):
    id: str
    sender: str
    sender_domain: str
    subject: str
    snippet: Optional[str]
    zone: ZoneType
    confidence: float
    reason: str
    jone5_message: str
    received_at: datetime
    classified_at: datetime
    corrected: bool = False
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    # Agent outputs - what makes jonE5 an actual AI agent
    summary: Optional[str] = None  # 1-2 sentence summary
    recommended_action: Optional[str] = None  # What to do
    action_type: Optional[str] = None  # reply, forward, call, archive, delegate
    draft_reply: Optional[str] = None  # Auto-generated reply
    llm_fallback: bool = False
    raw_body: Optional[str] = None  # Full email body content

class ZoneCorrection(BaseModel):
    message_id: str
    new_zone: ZoneType
    reason: Optional[str] = None

class JonE5Response(BaseModel):
    zone: ZoneType
    confidence: float
    reason: str
    personality_message: str
    summary: Optional[str] = None  # 1-2 sentence summary of the email
    recommended_action: Optional[str] = None  # What to do: "Call patient", "Forward to billing", etc.
    draft_reply: Optional[str] = None  # Auto-generated reply draft
    action_type: Optional[str] = None  # "reply", "forward", "call", "archive", "delegate"
    fallback: bool = False  # True when jonE5 had to use rules-based fallback


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.utcfromtimestamp(int(value))
        except Exception:
            return None


def _cache_nylas_grant(grant: dict) -> None:
    if not grant or 'grant_id' not in grant:
        return
    with nylas_grant_cache_lock:
        nylas_grant_cache[grant['grant_id']] = dict(grant)


def _get_cached_nylas_grant(grant_id: str) -> Optional[dict]:
    with nylas_grant_cache_lock:
        cached = nylas_grant_cache.get(grant_id)
    if cached:
        return dict(cached)
    record = db.get_nylas_grant_credentials(grant_id)
    if record:
        _cache_nylas_grant(record)
        return dict(record)
    return None


def ensure_nylas_grant_tokens(grant_id: str) -> Optional[dict]:
    """Refresh a grant's tokens when nearing expiry and keep cache/database aligned."""
    if not nylas_client:
        return None

    grant = _get_cached_nylas_grant(grant_id)
    if not grant:
        return None

    expires_at = _parse_iso_datetime(grant.get('expires_at'))
    refresh_token = grant.get('refresh_token')
    if not refresh_token or not expires_at:
        return grant

    if expires_at > datetime.utcnow() + NYLAS_REFRESH_HEADROOM:
        return grant

    try:
        refresh_response = nylas_client.auth.refresh_access_token({
            "client_id": NYLAS_CLIENT_ID,
            "client_secret": NYLAS_API_KEY,
            "refresh_token": refresh_token,
            "redirect_uri": NYLAS_CALLBACK_URI,
        })
    except Exception as exc:
        print(f"Nylas token refresh failed for {grant_id}: {exc}")
        return grant

    expires_in_value = getattr(refresh_response, 'expires_in', None)
    try:
        expires_in_seconds = int(expires_in_value) if expires_in_value else 3600
    except Exception:
        expires_in_seconds = 3600

    new_expires_at = (datetime.utcnow() + timedelta(seconds=expires_in_seconds)).isoformat()
    new_access_token = getattr(refresh_response, 'access_token', grant.get('access_token'))
    new_refresh_token = getattr(refresh_response, 'refresh_token', None) or refresh_token
    new_scope = getattr(refresh_response, 'scope', grant.get('scope'))
    new_token_type = getattr(refresh_response, 'token_type', grant.get('token_type'))

    grant.update({
        'access_token': new_access_token,
        'refresh_token': new_refresh_token,
        'expires_at': new_expires_at,
        'scope': new_scope,
        'token_type': new_token_type,
    })

    db.update_nylas_grant_tokens(
        grant_id,
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_at=new_expires_at,
        scope=new_scope,
        token_type=new_token_type,
    )
    _cache_nylas_grant(grant)
    return grant
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        user = db.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

class JonE5Classifier:
    STAT_KEYWORDS = ["critical", "urgent", "stat", "emergency", "abnormal", "positive", "elevated", "low", "high", "alert", "immediate", "asap"]
    STAT_DOMAINS = ["labcorp", "quest", "hospital", "er", "emergency", "lab", "pathology", "radiology"]
    TODAY_KEYWORDS = ["refill", "prescription", "prior auth", "authorization", "referral", "appointment", "callback", "pharmacy", "medication"]
    TODAY_DOMAINS = ["pharmacy", "cvs", "walgreens", "insurance", "medicaid", "medicare", "aetna", "cigna", "united", "bcbs"]
    THIS_WEEK_KEYWORDS = ["billing", "invoice", "payment", "claim", "denial", "records request", "compliance", "audit"]
    LATER_KEYWORDS = ["newsletter", "cme", "conference", "webinar", "marketing", "promotion", "sale", "discount", "survey"]
    
    PERSONALITY_MESSAGES = {
        "STAT": ["Doctor, I've detected a potentially urgent item. This one needs your attention.", "Sentinel alert: High-priority message detected. Please review promptly."],
        "TODAY": ["Zzzzip! Sorted! This one needs attention today!", "Input received! Routing to TODAY - action needed soon!"],
        "THIS_WEEK": ["Scanning... analyzing... okay! This can wait a few days.", "Sorted! This one goes to THIS WEEK - no rush!"],
        "LATER": ["Zoom zoom! Low priority detected! Filing to LATER!", "Input processed! This one can definitely wait!"]
    }
    
    CORRECTION_THANKS = ["Thank you! Correction received! Updating my circuits!", "Oh! I love learning from you! Adjustment logged!", "Correction accepted! My triage pathways are sharper already!"]
    
    def _check_keywords(self, text: str, keywords: list) -> tuple:
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True, keyword
        return False, ""
    
    def _check_domain(self, domain: str, domains: list) -> tuple:
        domain_lower = domain.lower()
        for d in domains:
            if d.lower() in domain_lower:
                return True, d
        return False, ""
    
    def _llm_classify(self, sender: str, sender_domain: str, subject: str, snippet: Optional[str] = None) -> Optional[JonE5Response]:
        """Use Cerebras LLM for full agent analysis - classification, summary, action, and draft reply."""
        if not cerebras_client:
            return None
        
        try:
            prompt = f"""You are jonE5, an AI medical office assistant. Analyze this email and provide actionable intelligence.

Email:
- From: {sender} ({sender_domain})
- Subject: {subject}
- Content: {snippet or 'No content available'}

Provide a complete analysis as JSON:
{{
  "zone": "STAT|TODAY|THIS_WEEK|LATER",
  "confidence": 0.0-1.0,
  "reason": "why this priority",
  "summary": "1-2 sentence summary of what this email is about and what they want",
  "recommended_action": "specific action like 'Call patient back about lab results' or 'Forward to billing department' or 'Archive - no action needed'",
  "action_type": "reply|forward|call|archive|delegate|review",
  "draft_reply": "If action_type is reply, write a professional 2-3 sentence response. Otherwise null."
}}

Zones:
- STAT: Urgent (critical labs, emergencies) - needs immediate action
- TODAY: Same-day (refills, prior auths, referrals) - needs response today  
- THIS_WEEK: Standard (billing, records) - can wait a few days
- LATER: FYI only (newsletters, marketing) - archive or ignore

Be specific and actionable. The doctor is overwhelmed with emails - help them know exactly what to do."""

            response = cerebras_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b",
                max_tokens=500,
                temperature=0.2
            )
            
            result_text = response.choices[0].message.content.strip()
            # Try to extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            zone = result.get("zone", "THIS_WEEK")
            if zone not in ["STAT", "TODAY", "THIS_WEEK", "LATER"]:
                zone = "THIS_WEEK"
            confidence = min(max(float(result.get("confidence", 0.75)), 0.0), 1.0)
            raw_draft = result.get("draft_reply")
            draft_reply = raw_draft if raw_draft not in (None, "null") else None
            fallback_flag = bool(result.get("action_type") == "reply" and not draft_reply)
            
            return JonE5Response(
                zone=zone,
                confidence=confidence,
                reason=result.get("reason", "AI analysis"),
                personality_message=random.choice(self.PERSONALITY_MESSAGES[zone]),
                summary=result.get("summary"),
                recommended_action=result.get("recommended_action"),
                action_type=result.get("action_type"),
                draft_reply=draft_reply,
                fallback=fallback_flag
            )
        except Exception as e:
            print(f"LLM classification error: {e}")
            return None
    
    def classify(self, sender: str, sender_domain: str, subject: str, snippet: Optional[str] = None) -> JonE5Response:
        """Classify email AND generate agent outputs (summary, action, draft reply)."""
        # ALWAYS use LLM for full agent analysis - this is what makes jonE5 an AI agent, not just a sorter
        if cerebras_client:
            llm_result = self._llm_classify(sender, sender_domain, subject, snippet)
            if llm_result:
                return llm_result
        
        # Fallback to rules-only if LLM is unavailable (no agent outputs)
        combined_text = f"{subject} {snippet or ''}"
        
        sender_key = f"sender:{sender.lower()}"
        override = db.get_rule_override(sender_key)
        if override:
            zone = override
            return JonE5Response(zone=zone, confidence=0.95, reason="Learned pattern from previous correction", personality_message=random.choice(self.PERSONALITY_MESSAGES[zone]),
                summary=f"Email from {sender} about: {subject[:50]}...", recommended_action="Review and take appropriate action", action_type="review", fallback=True)
        
        found, keyword = self._check_keywords(combined_text, self.STAT_KEYWORDS)
        if found:
            return JonE5Response(zone="STAT", confidence=0.92, reason=f"Urgent keyword: '{keyword}'", personality_message=random.choice(self.PERSONALITY_MESSAGES["STAT"]),
                summary=f"URGENT: Contains '{keyword}' - requires immediate attention", recommended_action="Review immediately and respond", action_type="review", fallback=True)
        
        found, domain = self._check_domain(sender_domain, self.STAT_DOMAINS)
        if found:
            return JonE5Response(zone="STAT", confidence=0.88, reason=f"High-priority domain: '{domain}'", personality_message=random.choice(self.PERSONALITY_MESSAGES["STAT"]),
                summary=f"From {domain} - likely urgent medical matter", recommended_action="Review lab/medical results immediately", action_type="review", fallback=True)
        
        found, keyword = self._check_keywords(combined_text, self.TODAY_KEYWORDS)
        if found:
            return JonE5Response(zone="TODAY", confidence=0.85, reason=f"Same-day keyword: '{keyword}'", personality_message=random.choice(self.PERSONALITY_MESSAGES["TODAY"]),
                summary=f"Action needed today: {keyword}", recommended_action=f"Process {keyword} request today", action_type="reply", fallback=True)
        
        found, domain = self._check_domain(sender_domain, self.TODAY_DOMAINS)
        if found:
            return JonE5Response(zone="TODAY", confidence=0.82, reason=f"Action-required sender: '{domain}'", personality_message=random.choice(self.PERSONALITY_MESSAGES["TODAY"]),
                summary=f"From {domain} - likely needs same-day response", recommended_action="Respond to request today", action_type="reply", fallback=True)
        
        found, keyword = self._check_keywords(combined_text, self.THIS_WEEK_KEYWORDS)
        if found:
            return JonE5Response(zone="THIS_WEEK", confidence=0.80, reason=f"Administrative keyword: '{keyword}'", personality_message=random.choice(self.PERSONALITY_MESSAGES["THIS_WEEK"]),
                summary=f"Administrative matter: {keyword}", recommended_action=f"Handle {keyword} within the week", action_type="delegate", fallback=True)
        
        found, keyword = self._check_keywords(combined_text, self.LATER_KEYWORDS)
        if found:
            return JonE5Response(zone="LATER", confidence=0.90, reason=f"Low-priority keyword: '{keyword}'", personality_message=random.choice(self.PERSONALITY_MESSAGES["LATER"]),
                summary=f"FYI only: {keyword}", recommended_action="Archive - no action needed", action_type="archive", fallback=True)
        
        return JonE5Response(zone="THIS_WEEK", confidence=0.60, reason="No strong signals - defaulting to THIS_WEEK", personality_message="Hmm... I'm not sure about this one. Putting it in THIS_WEEK for your review!",
            summary=f"Email from {sender}: {subject[:50]}...", recommended_action="Review and categorize manually", action_type="review", fallback=True)
    
    def get_correction_message(self) -> str:
        return random.choice(self.CORRECTION_THANKS)

jone5 = JonE5Classifier()

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "DocBoxRX API", "sentinel": "jonE5 online"}

def send_verification_email(email: str, name: str, verification_token: str):
    """Send verification email using Nylas or fallback method."""
    try:
        # Use Nylas to send email if we have a system grant
        # For now, we'll use a simple approach - in production, set up a system email account
        # TODO: Set up a system email account via Nylas for sending verification emails
        
        # For now, log the verification link (in production, send actual email)
        frontend_url = os.environ.get("FRONTEND_URL", "https://full-stack-apps-ah1tro24.devinapps.com")
        verification_url = f"{frontend_url}/verify-email?token={verification_token}"
        
        print(f"VERIFICATION EMAIL (send via your email service):")
        print(f"To: {email}")
        print(f"Subject: Verify your DocBoxRX account")
        print(f"Body: Hi {name},\n\nPlease verify your email by clicking this link:\n{verification_url}\n\nThis link expires in 24 hours.\n\nIf you didn't create this account, please ignore this email.")
        print(f"Verification URL: {verification_url}")
        
        # In production, integrate with:
        # - Nylas (if you have a system email account)
        # - SendGrid, Mailgun, or similar service
        # - AWS SES, Google Cloud Email API
        
    except Exception as e:
        print(f"Failed to send verification email: {e}")

@app.post("/api/auth/register")
async def register(user: UserCreate, background_tasks: BackgroundTasks):
    """
    Register a new user. Returns immediately, sends verification email in background.
    User must verify email before full account access.
    """
    if db.email_exists(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    # Create user as unverified
    new_user = db.create_user(user_id, user.email, user.name, user.practice_name, get_password_hash(user.password), is_verified=False)
    
    # Generate verification token
    verification_token = hashlib.sha256(f"{user_id}{user.email}{datetime.utcnow().isoformat()}{random.random()}".encode()).hexdigest()
    
    # Store verification token (expires in 24 hours)
    db.create_email_verification(user_id, user.email, verification_token, expires_in_hours=24)
    
    # Send verification email in background (non-blocking)
    background_tasks.add_task(send_verification_email, user.email, user.name, verification_token)
    
    # Return immediately with limited access token (user needs to verify email)
    access_token = create_access_token(data={"sub": user_id, "verified": False})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {k: v for k, v in new_user.items() if k != "hashed_password"},
        "message": "Registration successful! Please check your email to verify your account.",
        "requires_verification": True
    }

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """Fast login endpoint - optimized for speed."""
    try:
        # Trim and normalize email
        email = credentials.email.strip().lower() if credentials.email else ""
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        print(f"Login attempt for email: {email}")
        
        # Get user from database (with timeout protection)
        user = db.get_user_by_email(email)
        if not user:
            print(f"Login failed: User not found for email: {email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        print(f"User found: {user.get('id')}")
        
        # Verify password (bcrypt is fast, but check early)
        if not verify_password(credentials.password, user["hashed_password"]):
            print(f"Login failed: Invalid password for email: {email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        print(f"Password verified for: {email}")
        
        # Check if email is verified (only after password check passes)
        # For development: allow unverified logins with warning
        is_verified = bool(user.get("is_verified", False))
        if not is_verified:
            # Allow login but return warning - user can still access
            # In production, you may want to enforce verification
            print(f"WARNING: User {email} logging in without email verification")
            # Uncomment to enforce verification:
            # raise HTTPException(
            #     status_code=403, 
            #     detail="Email not verified. Please check your email and click the verification link."
            # )
        
        # Generate token (fast operation)
        access_token = create_access_token(data={"sub": user["id"], "verified": is_verified})
        
        print(f"Login successful for user: {email} (verified: {is_verified})")
        
        # Return immediately
        return Token(
            access_token=access_token, 
            token_type="bearer", 
            user={k: v for k, v in user.items() if k != "hashed_password"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/api/auth/verify-email")
async def verify_email(token: str):
    """Verify user email with token."""
    verification = db.get_email_verification(token)
    if not verification:
        return RedirectResponse(url=f"{os.environ.get('FRONTEND_URL', 'https://full-stack-apps-ah1tro24.devinapps.com')}?verify_error=invalid_token")
    
    # Verify the email
    success = db.verify_email(verification["user_id"], token)
    if success:
        return RedirectResponse(url=f"{os.environ.get('FRONTEND_URL', 'https://full-stack-apps-ah1tro24.devinapps.com')}?verify_success=true")
    else:
        return RedirectResponse(url=f"{os.environ.get('FRONTEND_URL', 'https://full-stack-apps-ah1tro24.devinapps.com')}?verify_error=verification_failed")

@app.post("/api/auth/resend-verification")
async def resend_verification(email: str, background_tasks: BackgroundTasks):
    """Resend verification email."""
    user = db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("is_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # Generate new verification token
    verification_token = hashlib.sha256(f"{user['id']}{email}{datetime.utcnow().isoformat()}{random.random()}".encode()).hexdigest()
    db.create_email_verification(user["id"], email, verification_token, expires_in_hours=24)
    
    # Send verification email in background
    background_tasks.add_task(send_verification_email, email, user.get("name", "User"), verification_token)
    
    return {"message": "Verification email sent. Please check your inbox."}

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k != "hashed_password"}

@app.post("/api/messages/ingest", response_model=MessageResponse)
async def ingest_email(email: EmailIngest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    sender_domain = email.sender_domain or (re.search(r'@([\w.-]+)', email.sender).group(1) if re.search(r'@([\w.-]+)', email.sender) else "unknown")
    classification = jone5.classify(sender=email.sender, sender_domain=sender_domain, subject=email.subject, snippet=email.snippet)
    message_id = str(uuid.uuid4())
    now = datetime.utcnow()
    message = {
        "id": message_id, "user_id": user_id, "sender": email.sender, "sender_domain": sender_domain,
        "subject": email.subject, "snippet": email.snippet, "zone": classification.zone,
        "confidence": classification.confidence, "reason": classification.reason,
        "jone5_message": classification.personality_message, "received_at": now.isoformat(),
        "classified_at": now.isoformat(), "corrected": False,
        # Agent outputs - what makes jonE5 an AI agent
        "summary": classification.summary,
        "recommended_action": classification.recommended_action,
        "action_type": classification.action_type,
        "draft_reply": classification.draft_reply,
        "llm_fallback": classification.fallback
    }
    db.create_message(message)
    return MessageResponse(**{**message, "received_at": now, "classified_at": now})

@app.get("/api/messages")
async def get_messages(zone: Optional[ZoneType] = None, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    messages = db.get_messages_by_user(user_id, zone)
    return {"messages": messages, "total": len(messages)}

@app.get("/api/messages/by-zone")
async def get_messages_by_zone(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    messages = db.get_messages_by_user(user_id)
    zones = {"STAT": [], "TODAY": [], "THIS_WEEK": [], "LATER": []}
    for msg in messages:
        zones[msg["zone"]].append(msg)
    return {"zones": zones, "counts": {zone: len(msgs) for zone, msgs in zones.items()}, "total": len(messages)}

@app.get("/api/messages/{message_id}/full")
async def get_full_message(message_id: str, current_user: dict = Depends(get_current_user)):
    """Get full email content - fetches from provider if not cached (jukebox-style access)."""
    user_id = current_user["id"]
    message = db.get_message_by_id(message_id, user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # If we have full content cached, return it immediately (jukebox - fast access)
    if message.get('raw_body') or message.get('raw_body_html'):
        return {
            "id": message_id,
            "raw_body": message.get('raw_body'),
            "raw_body_html": message.get('raw_body_html'),
            "cached": True
        }
    
    # If not cached, fetch from provider on-demand (jukebox - access when needed)
    provider_grant_id = message.get('provider_grant_id')
    provider_message_id = message.get('provider_message_id')
    
    if provider_grant_id and provider_message_id and nylas_client:
        try:
            grant_credentials = ensure_nylas_grant_tokens(provider_grant_id)
            if grant_credentials:
                # Fetch full message from Nylas (jukebox access)
                full_msg = nylas_client.messages.find(provider_grant_id, provider_message_id)
                if full_msg:
                    body_raw = getattr(full_msg, 'body', None) or (full_msg.get('body') if isinstance(full_msg, dict) else None)
                    body_html = getattr(full_msg, 'body_html', None) or (full_msg.get('body_html') if isinstance(full_msg, dict) else None)
                    
                    # Cache it in database for future fast access (jukebox caching)
                    db.update_message_full_content(message_id, user_id, body_raw, body_html)
                    
                    return {
                        "id": message_id,
                        "raw_body": body_raw,
                        "raw_body_html": body_html,
                        "cached": False
                    }
        except Exception as e:
            print(f"Failed to fetch full message from provider: {e}")
    
    # Fallback to snippet if available
    return {
        "id": message_id,
        "raw_body": message.get('snippet'),
        "raw_body_html": None,
        "cached": False
    }

@app.post("/api/messages/correct")
async def correct_message(correction: ZoneCorrection, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    message = db.get_message_by_id(correction.message_id, user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    old_zone = message["zone"]
    corrected_at = datetime.utcnow().isoformat()
    db.update_message_zone(correction.message_id, correction.new_zone, corrected_at)
    db.set_rule_override(f"sender:{message['sender'].lower()}", correction.new_zone)
    db.create_correction({"id": str(uuid.uuid4()), "user_id": user_id, "old_zone": old_zone, "new_zone": correction.new_zone, "sender": message["sender"], "corrected_at": corrected_at})
    message["zone"] = correction.new_zone
    message["corrected"] = True
    message["corrected_at"] = corrected_at
    return {"success": True, "message": message, "jone5_response": jone5.get_correction_message(), "learning": f"jonE5 will now route emails from '{message['sender']}' to {correction.new_zone}"}

@app.delete("/api/messages/{message_id}")
async def delete_message(message_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    message = db.get_message_by_id(message_id, user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    provider_feedback: dict[str, object] = {"provider_synced": False}
    provider_grant_id = message.get('provider_grant_id')
    provider_message_id = message.get('provider_message_id')

    if provider_grant_id and provider_message_id:
        if nylas_client:
            try:
                ensure_nylas_grant_tokens(provider_grant_id)
                nylas_client.messages.destroy(provider_grant_id, provider_message_id)
                provider_feedback['provider_synced'] = True
            except Exception as exc:
                provider_feedback['provider_error'] = str(exc)
        else:
            provider_feedback['provider_message'] = 'Provider sync unavailable; please delete from mailbox manually.'
    else:
        provider_feedback['provider_message'] = 'Local message; provider delete skipped.'

    if db.delete_message(message_id, user_id):
        provider_feedback.update({"success": True})
        return provider_feedback

    raise HTTPException(status_code=404, detail="Message not found")

@app.get("/api/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    messages = db.get_messages_by_user(user_id)
    corrections = db.get_corrections_by_user(user_id)
    zone_counts = {"STAT": 0, "TODAY": 0, "THIS_WEEK": 0, "LATER": 0}
    for msg in messages:
        zone_counts[msg["zone"]] += 1
    return {"total_messages": len(messages), "total_corrections": len(corrections), "zone_counts": zone_counts}

# ============== ACTION CENTER API ==============
# One-click actions for email workflow management

class MessageStatusUpdate(BaseModel):
    status: str  # 'done', 'archived', 'snoozed', 'active'
    snoozed_until: Optional[str] = None  # ISO datetime for snooze

@app.get("/api/action-center")
async def get_action_center(current_user: dict = Depends(get_current_user)):
    """Get the Action Center / Daily Brief data."""
    user_id = current_user["id"]
    action_items = db.get_action_items(user_id)
    return {
        "urgent_count": len(action_items["urgent_items"]),
        "needs_reply_count": len(action_items["needs_reply"]),
        "snoozed_due_count": len(action_items["snoozed_due"]),
        "done_today": action_items["done_today"],
        "total_action_items": action_items["total_action_items"],
        "urgent_items": action_items["urgent_items"][:5],  # Top 5 urgent items
        "needs_reply": action_items["needs_reply"][:5],  # Top 5 needing reply
        "snoozed_due": action_items["snoozed_due"]
    }

@app.post("/api/messages/{message_id}/status")
async def update_message_status(message_id: str, update: MessageStatusUpdate, current_user: dict = Depends(get_current_user)):
    """Update message status (done, archived, snoozed, active)."""
    user_id = current_user["id"]
    message = db.get_message_by_id(message_id, user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    provider_feedback: dict[str, object] = {"provider_synced": False}
    provider_unread = message.get('provider_unread')
    provider_folders = message.get('provider_folders', []) or []
    provider_grant_id = message.get('provider_grant_id')
    provider_message_id = message.get('provider_message_id')

    provider_request: dict[str, object] = {}

    if provider_grant_id and provider_message_id:
        if nylas_client:
            if update.status == 'done':
                provider_request['unread'] = False
                provider_unread = False
            elif update.status == 'active':
                provider_request['unread'] = True
                provider_unread = True
            elif update.status == 'archived':
                cleaned_folders = [folder for folder in provider_folders if isinstance(folder, str) and folder.lower() != 'inbox']
                if not cleaned_folders:
                    cleaned_folders = ['archive']
                provider_request['folders'] = cleaned_folders
                provider_request['unread'] = False
                provider_unread = False
                provider_folders = cleaned_folders
            elif update.status == 'snoozed':
                provider_feedback['provider_message'] = 'Provider snooze not supported; manual follow-up required.'

            if provider_request:
                try:
                    ensure_nylas_grant_tokens(provider_grant_id)
                    nylas_client.messages.update(provider_grant_id, provider_message_id, provider_request)
                    provider_feedback['provider_synced'] = True
                except Exception as exc:
                    provider_feedback['provider_error'] = str(exc)
            elif 'provider_message' not in provider_feedback:
                provider_feedback['provider_message'] = 'No provider update performed.'
        else:
            provider_feedback['provider_message'] = 'Provider sync unavailable; please update mailbox manually.'
    else:
        provider_feedback['provider_message'] = 'Local message; provider sync skipped.'

    if not db.update_message_status(message_id, user_id, update.status, update.snoozed_until):
        raise HTTPException(status_code=404, detail="Message not found")

    if provider_feedback.get('provider_synced'):
        db.update_message_provider_state(
            message_id,
            user_id,
            provider_unread=provider_unread,
            provider_folders=provider_folders,
        )

    provider_feedback.update({
        "success": True,
        "status": update.status,
    })
    return provider_feedback

@app.post("/api/messages/{message_id}/replied")
async def mark_message_replied(message_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a message as replied (clears needs_reply flag)."""
    user_id = current_user["id"]
    if db.mark_message_replied(message_id, user_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Message not found")

@app.post("/api/demo/seed")
async def seed_demo_data(current_user: dict = Depends(get_current_user)):
    demo_emails = [
        {"sender": "results@labcorp.com", "subject": "CRITICAL: Abnormal CBC Results for Patient", "snippet": "Hemoglobin critically low at 6.2 g/dL. Immediate attention required."},
        {"sender": "alerts@questdiagnostics.com", "subject": "STAT: Potassium Level Alert", "snippet": "Critical potassium level detected: 6.8 mEq/L"},
        {"sender": "pharmacy@cvs.com", "subject": "Refill Request - Metformin 500mg", "snippet": "Patient requesting a refill for Metformin 500mg, 90 day supply."},
        {"sender": "priorauth@aetna.com", "subject": "Prior Authorization Required", "snippet": "Prior authorization needed for MRI lumbar spine."},
        {"sender": "billing@medicaid.gov", "subject": "Claim Denial Notice", "snippet": "Claim #12345 has been denied. Reason: Missing documentation."},
        {"sender": "records@hospital.org", "subject": "Medical Records Request", "snippet": "Request for medical records for patient transfer."},
        {"sender": "newsletter@medscape.com", "subject": "Weekly CME Update", "snippet": "This week's continuing medical education opportunities..."},
        {"sender": "marketing@dentalequip.com", "subject": "50% Off Dental Supplies!", "snippet": "Limited time offer on all dental equipment and supplies."},
    ]
    results = []
    for email_data in demo_emails:
        email = EmailIngest(**email_data)
        result = await ingest_email(email, current_user)
        results.append({"subject": email_data["subject"], "zone": result.zone})
    return {"seeded": len(results), "results": results}

# ============== SOURCES API ==============
# Manage email sources (Gmail, Yahoo, Outlook accounts)

INBOUND_DOMAIN = os.environ.get("INBOUND_DOMAIN", "inbound.docboxrx.com")

def generate_inbound_token() -> str:
    """Generate a unique token for inbound email routing."""
    return hashlib.sha256(f"{uuid.uuid4()}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]

@app.post("/api/sources", response_model=EmailSource)
async def create_source(source: SourceCreate, current_user: dict = Depends(get_current_user)):
    """Create a new email source (e.g., Gmail Personal, Work Outlook)."""
    user_id = current_user["id"]
    source_id = str(uuid.uuid4())
    token = generate_inbound_token()
    
    new_source = {
        "id": source_id,
        "user_id": user_id,
        "name": source.name,
        "inbound_token": token,
        "inbound_address": f"inbox-{token}@{INBOUND_DOMAIN}",
        "created_at": datetime.utcnow().isoformat(),
        "email_count": 0
    }
    
    db.create_source(new_source)
    return EmailSource(**new_source)

@app.get("/api/sources")
async def get_sources(current_user: dict = Depends(get_current_user)):
    """Get all email sources for the current user."""
    user_id = current_user["id"]
    sources = db.get_sources_by_user(user_id)
    return {"sources": sources, "total": len(sources)}

@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an email source."""
    user_id = current_user["id"]
    if db.delete_source(source_id, user_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Source not found")

# ============== INBOUND EMAIL WEBHOOK ==============
# Receives forwarded emails from email services (Mailgun, SendGrid, CloudMailin, etc.)

# Default user for CloudMailin emails (created on first email if needed)
CLOUDMAILIN_USER_ID = "cloudmailin-default-user"

@app.post("/api/inbound/cloudmailin")
async def cloudmailin_webhook(request: Request):
    """
    Dedicated CloudMailin webhook endpoint.
    Emails received here are stored for the default CloudMailin user.
    
    IMPORTANT: This endpoint does NOT log request bodies to protect PHI.
    """
    # Parse the incoming email based on content type
    content_type = request.headers.get("content-type", "")
    
    sender = None
    subject = None
    snippet = None
    
    raw_headers = None
    raw_body = None
    if "application/json" in content_type:
        # JSON payload (CloudMailin normalized format)
        try:
            data = await request.json()
            # CloudMailin JSON format has headers object and envelope
            headers = data.get("headers", {})
            envelope = data.get("envelope", {})

            # Store raw headers and body as safe strings (not logged)
            try:
                raw_headers = json.dumps(headers)
            except Exception:
                raw_headers = str(headers)
            try:
                # Prefer raw MIME if present, otherwise store full JSON
                raw_body = data.get('raw') or data.get('email') or json.dumps(data)
            except Exception:
                raw_body = str(data)
            
            # Try multiple paths for sender
            sender = headers.get("from") or headers.get("From") or envelope.get("from") or data.get("from")
            # Try multiple paths for subject
            subject = headers.get("subject") or headers.get("Subject") or data.get("subject")
            # Get FULL body content (no truncation) - prefer plain text, fallback to HTML
            snippet = data.get("plain") or data.get("text") or data.get("html") or ""
        except Exception as e:
            print(f"CloudMailin JSON parse error: {e}")
    
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        # Multipart form data (CloudMailin multipart format)
        try:
            form = await request.form()
            sender = form.get("from") or form.get("sender")
            subject = form.get("subject")
            # Get FULL body content (no truncation) - prefer plain text, fallback to HTML
            snippet = form.get("plain") or form.get("text") or form.get("html") or ""

            # Attempt to capture raw body or forwarded raw MIME
            raw_body = form.get('email') or form.get('raw') or None
            raw_headers = form.get('headers') or raw_headers
        except Exception as e:
            print(f"CloudMailin form parse error: {e}")
    
    if not sender or not subject:
        # Return 200 anyway to prevent CloudMailin from retrying
        return {"success": False, "error": "Could not parse email - missing sender or subject", "received": True}
    
    # Extract domain from sender
    sender_domain = "unknown"
    domain_match = re.search(r'@([\w.-]+)', sender)
    if domain_match:
        sender_domain = domain_match.group(1)
    
    # Classify with jonE5
    classification = jone5.classify(sender=sender, sender_domain=sender_domain, subject=subject, snippet=snippet)
    
    # Store message for CloudMailin user
    message_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    message = {
        "id": message_id,
        "user_id": CLOUDMAILIN_USER_ID,
        "sender": sender,
        "sender_domain": sender_domain,
        "subject": subject,
        "snippet": snippet,
        "zone": classification.zone,
        "confidence": classification.confidence,
        "reason": classification.reason,
        "jone5_message": classification.personality_message,
        "received_at": now.isoformat(),
        "classified_at": now.isoformat(),
        "corrected": False,
        "source_id": "cloudmailin",
        "source_name": "CloudMailin",
        "raw_headers": raw_headers,
        "raw_body": raw_body,
        "llm_fallback": getattr(classification, 'fallback', False),
        "status": 'active'
    }
    
    db.create_cloudmailin_message(message)
    
    return {
        "success": True,
        "message_id": message_id,
        "zone": classification.zone,
        "jone5_says": classification.personality_message
    }

@app.get("/api/cloudmailin/messages")
async def get_cloudmailin_messages():
    """Get all messages received via CloudMailin (no auth required for demo)."""
    messages = db.get_cloudmailin_messages()
    zones = {"STAT": [], "TODAY": [], "THIS_WEEK": [], "LATER": []}
    for msg in messages:
        zones.get(msg.get("zone", "THIS_WEEK"), []).append(msg)
    return {"zones": zones, "counts": {zone: len(msgs) for zone, msgs in zones.items()}, "total": len(messages)}


@app.post("/api/cloudmailin/messages/{message_id}/status")
async def cloudmailin_update_status(message_id: str, update: MessageStatusUpdate):
    """Update cloudmailin message status (done, archived, snoozed, active)."""
    if db.update_cloudmailin_message_status(message_id, update.status, update.snoozed_until):
        return {"success": True, "status": update.status}
    raise HTTPException(status_code=404, detail="CloudMailin message not found")


@app.delete("/api/cloudmailin/messages/{message_id}")
async def cloudmailin_delete_message(message_id: str):
    """Delete a cloudmailin message."""
    if db.delete_cloudmailin_message(message_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="CloudMailin message not found")

def parse_forwarded_email(raw_email: str) -> dict:
    """Parse a forwarded email to extract original sender, subject, and snippet."""
    try:
        msg = email.message_from_string(raw_email, policy=policy.default)
        
        # Get basic headers
        sender = msg.get("From", "unknown@unknown.com")
        subject = msg.get("Subject", "No Subject")
        
        # Get FULL body content (no truncation)
        snippet = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        snippet = part.get_content()
                    except:
                        pass
                    break
        else:
            try:
                snippet = msg.get_content() if hasattr(msg, 'get_content') else ""
            except:
                pass
        
        return {
            "sender": sender,
            "subject": subject,
            "snippet": snippet.strip() if snippet else None
        }
    except Exception as e:
        print(f"Email parsing error: {e}")
        return None

@app.post("/api/inbound/{token}")
async def inbound_email_webhook(token: str, request: Request):
    """
    Webhook endpoint for receiving forwarded emails.
    Compatible with Mailgun, SendGrid, CloudMailin, etc.
    
    IMPORTANT: This endpoint does NOT log request bodies to protect PHI.
    """
    source = db.get_source_by_token(token)
    if not source:
        raise HTTPException(status_code=404, detail="Invalid inbound token")
    
    user_id = source["user_id"]
    source_id = source["id"]
    source_name = source["name"]
    
    # Parse the incoming email based on content type
    content_type = request.headers.get("content-type", "")
    
    sender = None
    subject = None
    snippet = None
    
    if "application/json" in content_type:
        # JSON payload (CloudMailin, custom integrations)
        try:
            data = await request.json()
            sender = data.get("from") or data.get("sender") or data.get("envelope", {}).get("from")
            subject = data.get("subject") or data.get("headers", {}).get("subject")
            # Get FULL body content (no truncation)
            snippet = data.get("text") or data.get("plain") or data.get("body") or ""
        except:
            pass
    
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        # Form data (Mailgun, SendGrid)
        try:
            form = await request.form()
            sender = form.get("from") or form.get("sender")
            subject = form.get("subject")
            # Get FULL body content (no truncation)
            snippet = form.get("stripped-text") or form.get("text") or form.get("body-plain") or ""
            
            # If raw email is provided, parse it
            if form.get("email"):
                parsed = parse_forwarded_email(form.get("email"))
                if parsed:
                    sender = sender or parsed["sender"]
                    subject = subject or parsed["subject"]
                    snippet = snippet or parsed["snippet"]
        except:
            pass
    
    else:
        # Raw email (some providers send raw MIME)
        try:
            body = await request.body()
            raw_body = body.decode("utf-8", errors="ignore")
            parsed = parse_forwarded_email(raw_body)
            if parsed:
                sender = parsed["sender"]
                subject = parsed["subject"]
                snippet = parsed["snippet"]
        except:
            pass
    
    if not sender or not subject:
        raise HTTPException(status_code=400, detail="Could not parse email - missing sender or subject")
    
    # Extract domain from sender
    sender_domain = "unknown"
    domain_match = re.search(r'@([\w.-]+)', sender)
    if domain_match:
        sender_domain = domain_match.group(1)
    
    # Classify with jonE5
    classification = jone5.classify(sender=sender, sender_domain=sender_domain, subject=subject, snippet=snippet)
    
    # Store message
    message_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    message = {
        "id": message_id,
        "user_id": user_id,
        "sender": sender,
        "sender_domain": sender_domain,
        "subject": subject,
        "snippet": snippet,
        "zone": classification.zone,
        "confidence": classification.confidence,
        "reason": classification.reason,
        "jone5_message": classification.personality_message,
        "received_at": now.isoformat(),
        "classified_at": now.isoformat(),
        "corrected": False,
        "source_id": source_id,
        "source_name": source_name
    }
    
    db.create_message(message)
    db.increment_source_email_count(source_id)
    
    return {
        "success": True,
        "message_id": message_id,
        "zone": classification.zone,
        "jone5_says": classification.personality_message
    }

@app.get("/api/messages/by-source/{source_id}")
async def get_messages_by_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """Get all messages from a specific source."""
    user_id = current_user["id"]
    messages = db.get_messages_by_user(user_id)
    filtered = [m for m in messages if m.get("source_id") == source_id]
    return {"messages": filtered, "total": len(filtered)}

# ============== NYLAS EMAIL INTEGRATION ==============
# Universal email connection via Nylas (Gmail, Outlook, Yahoo, etc.)

@app.get("/api/nylas/auth-url")
async def get_nylas_auth_url(provider: str = "google", current_user: dict = Depends(get_current_user)):
    """Generate Nylas OAuth URL for connecting an email account."""
    if not nylas_client or not NYLAS_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Nylas not configured")
    
    # Include user_id in state so we can link the grant to the user after callback
    state = current_user["id"]
    
    # Build auth URL with provider to force Google/Microsoft OAuth instead of IMAP
    auth_url = nylas_client.auth.url_for_oauth2({
        "client_id": NYLAS_CLIENT_ID,
        "redirect_uri": NYLAS_CALLBACK_URI,
        "state": state,
        "provider": provider,  # Force specific provider (google, microsoft, imap)
    })
    
    return {"auth_url": auth_url, "provider": provider}

@app.get("/api/nylas/callback")
async def nylas_oauth_callback(code: str, state: str = None, background_tasks: BackgroundTasks = None):
    """Handle Nylas OAuth callback, exchange code for grant, and auto-sync top 5 emails."""
    from fastapi.responses import RedirectResponse
    
    frontend_url = os.environ.get("FRONTEND_URL", "https://full-stack-apps-ah1tro24.devinapps.com")
    
    if not nylas_client:
        return RedirectResponse(url=f"{frontend_url}?nylas_error=Nylas+not+configured")
    
    try:
        # Exchange code for token/grant
        response = nylas_client.auth.exchange_code_for_token({
            "client_id": NYLAS_CLIENT_ID,
            "client_secret": NYLAS_API_KEY,
            "code": code,
            "redirect_uri": NYLAS_CALLBACK_URI,
        })
        
        grant_id = response.grant_id
        email = response.email if hasattr(response, 'email') else "unknown@email.com"
        
        provider = getattr(response, 'provider', None)
        access_token = getattr(response, 'access_token', None)
        refresh_token = getattr(response, 'refresh_token', None)
        token_type = getattr(response, 'token_type', None)
        scopes_attr = getattr(response, 'scopes', None) or getattr(response, 'scope', None)
        if isinstance(scopes_attr, (list, tuple, set)):
            scope = ' '.join(str(item) for item in scopes_attr)
        else:
            scope = scopes_attr

        expires_at = None
        expires_in = getattr(response, 'expires_in', None)
        if expires_in:
            try:
                expires_at = (datetime.utcnow() + timedelta(seconds=int(expires_in))).isoformat()
            except Exception:
                expires_at = None
        else:
            raw_expires_at = getattr(response, 'expires_at', None)
            if raw_expires_at:
                if isinstance(raw_expires_at, datetime):
                    expires_at = raw_expires_at.isoformat()
                else:
                    try:
                        expires_at = datetime.utcfromtimestamp(int(raw_expires_at)).isoformat()
                    except Exception:
                        if isinstance(raw_expires_at, str):
                            expires_at = raw_expires_at

        existing_record = db.get_nylas_grant_by_grant_id(grant_id)
        
        # Handle registration flow: state might be email or temp identifier
        # If state is email, try to find user by email
        user_id = state
        if state and '@' in state:
            # State is an email, find user by email
            user = db.get_user_by_email(state)
            if user:
                user_id = user['id']
            else:
                # User not created yet - store grant temporarily with email as identifier
                # Will be linked when user registers
                user_id = None
        
        # If we have existing record, use its user_id
        if existing_record and existing_record.get('user_id'):
            user_id = existing_record['user_id']
        
        # If still no user_id, check if state is a valid UUID (user_id)
        if not user_id or user_id == state:
            # Try to validate if state is a UUID
            try:
                uuid.UUID(state)
                user_id = state  # Valid UUID, use as user_id
            except (ValueError, TypeError):
                pass
        
        # If no user_id found, store grant with email identifier for later linking
        if not user_id:
            # Store grant with email as temporary identifier
            grant_record = {
                "id": existing_record['id'] if existing_record and existing_record.get('id') else str(uuid.uuid4()),
                "user_id": email,  # Temporary: use email as identifier
                "grant_id": grant_id,
                "email": email,
                "provider": provider,
                "created_at": existing_record['created_at'] if existing_record and existing_record.get('created_at') else datetime.utcnow().isoformat(),
                "last_sync_at": existing_record.get('last_sync_at') if existing_record else None,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "token_type": token_type,
                "scope": scope,
            }
            db.create_nylas_grant(grant_record)
            # Redirect to registration with email pre-filled
            return RedirectResponse(url=f"{frontend_url}?nylas_pending=true&email={email}&grant_id={grant_id}")

        if existing_record and existing_record.get('user_id') and existing_record['user_id'] != user_id and '@' not in str(existing_record['user_id']):
            return RedirectResponse(url=f"{frontend_url}?nylas_error=Grant+already+linked+to+another+user")

        grant_record = {
            "id": existing_record['id'] if existing_record and existing_record.get('id') else str(uuid.uuid4()),
            "user_id": user_id,
            "grant_id": grant_id,
            "email": email,
            "provider": provider,
            "created_at": existing_record['created_at'] if existing_record and existing_record.get('created_at') else datetime.utcnow().isoformat(),
            "last_sync_at": existing_record.get('last_sync_at') if existing_record else None,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "token_type": token_type,
            "scope": scope,
        }

        db.create_nylas_grant(grant_record)
        stored_grant = db.get_nylas_grant_credentials(grant_id)
        if stored_grant:
            _cache_nylas_grant(stored_grant)
        
        # AUTO-SYNC top 5 emails immediately (background task) - no manual sync needed!
        if background_tasks and user_id:
            background_tasks.add_task(auto_sync_emails, grant_id, user_id, limit=5)
        
        # Redirect back to frontend with success
        return RedirectResponse(url=f"{frontend_url}?nylas_success=true&email={email}&auto_sync=true")
    except Exception as e:
        # Redirect back to frontend with error
        error_msg = str(e).replace(" ", "+")
        return RedirectResponse(url=f"{frontend_url}?nylas_error={error_msg}")

def auto_sync_emails(grant_id: str, user_id: str, limit: int = 5):
    """Auto-sync top emails from a connected account (background task)."""
    try:
        if not nylas_client:
            return
        
        grant_credentials = ensure_nylas_grant_tokens(grant_id)
        if not grant_credentials:
            print(f"Failed to get grant credentials for {grant_id}")
            return
        
        # Fetch top emails from Nylas
        messages_response = nylas_client.messages.list(
            grant_id,
            query_params={"limit": limit, "in": ["INBOX"], "view": "expanded"}
        )
        
        for msg in messages_response.data:
            # Extract email details
            from_list = msg.from_ if hasattr(msg, 'from_') else msg.get('from', [])
            if from_list:
                first_from = from_list[0]
                if hasattr(first_from, 'email'):
                    sender = first_from.email
                    sender_name = first_from.name if hasattr(first_from, 'name') and first_from.name else sender
                elif isinstance(first_from, dict):
                    sender = first_from.get('email', 'unknown@unknown.com')
                    sender_name = first_from.get('name', sender)
                else:
                    sender = "unknown@unknown.com"
                    sender_name = sender
            else:
                sender = "unknown@unknown.com"
                sender_name = sender
            
            subject = msg.subject if hasattr(msg, 'subject') else msg.get('subject', 'No Subject') or 'No Subject'
            
            # Get full email body
            body_raw = None
            body_html = None
            if hasattr(msg, 'body'):
                body_raw = msg.body
            elif isinstance(msg, dict) and 'body' in msg:
                body_raw = msg.get('body')
            if hasattr(msg, 'body_html'):
                body_html = msg.body_html
            elif isinstance(msg, dict) and 'body_html' in msg:
                body_html = msg.get('body_html')
            
            snippet_raw = msg.snippet if hasattr(msg, 'snippet') else msg.get('snippet', None)
            snippet = body_raw or (body_html if body_html else snippet_raw)
            
            sender_domain = "unknown"
            domain_match = re.search(r'@([\w.-]+)', sender)
            if domain_match:
                sender_domain = domain_match.group(1)
            
            # Classify with jonE5
            classification = jone5.classify(
                sender=f"{sender_name} <{sender}>",
                sender_domain=sender_domain,
                subject=subject,
                snippet=snippet
            )
            
            # Store message
            message_id = str(uuid.uuid4())
            now = datetime.utcnow()
            provider_message_id = getattr(msg, 'id', None) or msg.get('id')
            provider_thread_id = getattr(msg, 'thread_id', None) or msg.get('thread_id')
            
            grant = db.get_nylas_grant_by_grant_id(grant_id)
            message = {
                "id": message_id,
                "user_id": user_id,
                "sender": f"{sender_name} <{sender}>",
                "sender_domain": sender_domain,
                "subject": subject,
                "snippet": snippet,
                "zone": classification.zone,
                "confidence": classification.confidence,
                "reason": classification.reason,
                "jone5_message": classification.personality_message,
                "received_at": now.isoformat(),
                "classified_at": now.isoformat(),
                "corrected": False,
                "source_id": f"nylas-{grant_id}",
                "source_name": f"Nylas: {email}",
                "provider_message_id": provider_message_id,
                "provider_thread_id": provider_thread_id,
                "provider_grant_id": grant_id,
                "provider_folders": [],
                "provider_unread": True,
                "llm_fallback": classification.fallback,
                "raw_body": body_raw or body_html or snippet,
                "raw_body_html": body_html,
            }
            
            db.create_message(message)
        
        # Update last sync time
        db.update_nylas_grant_sync_time(grant_id, datetime.utcnow().isoformat())
        print(f"Auto-synced {len(messages_response.data)} emails from {email}")
    except Exception as e:
        print(f"Auto-sync failed for grant {grant_id}: {e}")

@app.get("/api/nylas/grants")
async def get_nylas_grants(current_user: dict = Depends(get_current_user)):
    """Get all connected email accounts for the current user."""
    user_id = current_user["id"]
    grants = db.get_nylas_grants_by_user(user_id)
    return {"grants": grants, "total": len(grants)}

@app.delete("/api/nylas/grants/{grant_id}")
async def delete_nylas_grant(grant_id: str, current_user: dict = Depends(get_current_user)):
    """Disconnect an email account."""
    user_id = current_user["id"]
    if db.delete_nylas_grant(grant_id, user_id):
        with nylas_grant_cache_lock:
            nylas_grant_cache.pop(grant_id, None)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Grant not found")

@app.post("/api/nylas/sync/{grant_id}")
async def sync_nylas_emails(grant_id: str, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Sync recent emails from a connected account and classify with jonE5."""
    if not nylas_client:
        raise HTTPException(status_code=500, detail="Nylas not configured")
    
    user_id = current_user["id"]
    
    # Verify grant belongs to user
    grants = db.get_nylas_grants_by_user(user_id)
    grant = next((g for g in grants if g['grant_id'] == grant_id), None)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    
    grant_credentials = ensure_nylas_grant_tokens(grant_id)

    try:
        # Fetch recent messages from Nylas with full content
        messages_response = nylas_client.messages.list(
            grant_id,
            query_params={"limit": limit, "in": ["INBOX"], "view": "expanded"}  # Get expanded view for full content
        )
        
        classified_count = 0
        results = []
        
        for msg in messages_response.data:
            # Extract email details - handle both object and dict formats
            from_list = msg.from_ if hasattr(msg, 'from_') else msg.get('from', [])
            if from_list:
                first_from = from_list[0]
                if hasattr(first_from, 'email'):
                    sender = first_from.email
                    sender_name = first_from.name if hasattr(first_from, 'name') and first_from.name else sender
                elif isinstance(first_from, dict):
                    sender = first_from.get('email', 'unknown@unknown.com')
                    sender_name = first_from.get('name', sender)
                else:
                    sender = "unknown@unknown.com"
                    sender_name = sender
            else:
                sender = "unknown@unknown.com"
                sender_name = sender
            
            subject = msg.subject if hasattr(msg, 'subject') else msg.get('subject', 'No Subject') or 'No Subject'
            
            # Get provider message ID first (needed for fetching full content)
            provider_message_id = getattr(msg, 'id', None)
            if provider_message_id is None and isinstance(msg, dict):
                provider_message_id = msg.get('id')
            
            # Get FULL email body - fetch complete message if needed (jukebox-style)
            body_raw = None
            body_html = None
            
            # Try to get body from message object
            if hasattr(msg, 'body'):
                body_raw = msg.body
            elif isinstance(msg, dict) and 'body' in msg:
                body_raw = msg.get('body')
            
            # Try to get HTML body
            if hasattr(msg, 'body_html'):
                body_html = msg.body_html
            elif isinstance(msg, dict) and 'body_html' in msg:
                body_html = msg.get('body_html')
            
            # If we don't have body, fetch full message from Nylas (jukebox access)
            if not body_raw and not body_html and provider_message_id:
                try:
                    # Fetch full message details on-demand
                    full_msg = nylas_client.messages.find(grant_id, provider_message_id)
                    if full_msg:
                        body_raw = getattr(full_msg, 'body', None) or (full_msg.get('body') if isinstance(full_msg, dict) else None)
                        body_html = getattr(full_msg, 'body_html', None) or (full_msg.get('body_html') if isinstance(full_msg, dict) else None)
                except Exception as e:
                    print(f"Failed to fetch full message {provider_message_id}: {e}")
            
            # Fallback to snippet if no body available
            snippet_raw = msg.snippet if hasattr(msg, 'snippet') else msg.get('snippet', None)
            # Prefer plain text, then HTML, then snippet
            snippet = body_raw or (body_html if body_html else snippet_raw)
            
            # Extract domain from sender
            sender_domain = "unknown"
            domain_match = re.search(r'@([\w.-]+)', sender)
            if domain_match:
                sender_domain = domain_match.group(1)

            folders_attr = getattr(msg, 'folders', None)
            if folders_attr is None and isinstance(msg, dict):
                folders_attr = msg.get('folders', [])
            provider_folders = list(folders_attr or [])

            provider_unread = getattr(msg, 'unread', None)
            if provider_unread is None and isinstance(msg, dict):
                provider_unread = msg.get('unread')
            if provider_unread is not None:
                provider_unread = bool(provider_unread)
            
            # Classify with jonE5
            classification = jone5.classify(
                sender=f"{sender_name} <{sender}>",
                sender_domain=sender_domain,
                subject=subject,
                snippet=snippet
            )
            
            # Store message
            message_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            provider_message_id = getattr(msg, 'id', None)
            if provider_message_id is None and isinstance(msg, dict):
                provider_message_id = msg.get('id')

            provider_thread_id = getattr(msg, 'thread_id', None)
            if provider_thread_id is None and isinstance(msg, dict):
                provider_thread_id = msg.get('thread_id')

            message = {
                "id": message_id,
                "user_id": user_id,
                "sender": f"{sender_name} <{sender}>",
                "sender_domain": sender_domain,
                "subject": subject,
                "snippet": snippet,
                "zone": classification.zone,
                "confidence": classification.confidence,
                "reason": classification.reason,
                "jone5_message": classification.personality_message,
                "received_at": now.isoformat(),
                "classified_at": now.isoformat(),
                "corrected": False,
                "source_id": f"nylas-{grant_id}",
                "source_name": f"Nylas: {grant['email']}",
                "provider_message_id": provider_message_id,
                "provider_thread_id": provider_thread_id,
                "provider_grant_id": grant_id,
                "provider_folders": provider_folders,
                "provider_unread": provider_unread,
                "llm_fallback": classification.fallback,
                "raw_body": body_raw or body_html or snippet,  # Store full body as raw_body
                "raw_body_html": body_html,  # Store HTML version if available
            }
            
            db.create_message(message)
            classified_count += 1
            results.append({"subject": subject, "zone": classification.zone})
        
        # Update last sync time
        last_sync_timestamp = datetime.utcnow().isoformat()
        db.update_nylas_grant_sync_time(grant_id, last_sync_timestamp)
        if grant_credentials:
            grant_credentials['last_sync_at'] = last_sync_timestamp
            _cache_nylas_grant(grant_credentials)
        
        return {
            "success": True,
            "synced": classified_count,
            "results": results,
            "jone5_says": "Zoom zoom! Emails synced and classified!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.get("/api/nylas/webhook")
async def nylas_webhook_challenge(challenge: Optional[str] = None):
    """Handle Nylas webhook challenge verification."""
    if challenge:
        return challenge
    return {"status": "ok"}


@app.post("/api/nylas/webhook")
async def nylas_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Nylas message.created events and trigger Shadow Worker."""
    data = await request.json()

    deltas = data.get("deltas") if isinstance(data, dict) else None
    if isinstance(deltas, list):
        for delta in deltas:
            if not isinstance(delta, dict):
                continue
            if delta.get("type") != "message.created":
                continue
            obj_data = delta.get("object_data") or {}
            if not isinstance(obj_data, dict):
                continue
            msg_id = obj_data.get("id")
            grant_id = obj_data.get("grant_id")
            if msg_id and grant_id:
                print(f"🔔 Webhook Received: New Message {msg_id}")
                background_tasks.add_task(process_shadow_traffic, grant_id, msg_id)

    return {"status": "success"}


@app.post("/api/nylas/webhook/test")
async def nylas_shadow_test(
    grant_id: str,
    message_id: str,
    repeat: int = 1,
    current_user: dict = Depends(get_current_user),
):
    """Test endpoint to trigger Shadow Worker manually (authenticated)."""
    if repeat < 1:
        repeat = 1
    if repeat > 50:
        repeat = 50

    for _ in range(repeat):
        await process_shadow_traffic(grant_id, message_id)

    return {"status": "ok", "repeat": repeat, "grant_id": grant_id, "message_id": message_id}


class SendReplyRequest(BaseModel):
    message_id: str
    reply_body: str
    grant_id: Optional[str] = None  # If provided, use this grant to send. Otherwise, find grant from message.

@app.post("/api/messages/{message_id}/send-reply")
async def send_reply(message_id: str, request: SendReplyRequest, current_user: dict = Depends(get_current_user)):
    """Send a reply email via Nylas API."""
    if not nylas_client:
        raise HTTPException(status_code=500, detail="Nylas not configured - cannot send emails")
    
    user_id = current_user["id"]
    
    # Get the original message
    message = db.get_message_by_id(message_id, user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Determine which grant to use for sending
    grant_id = request.grant_id or message.get('provider_grant_id')
    if not grant_id:
        # Try to find a grant for this user
        grants = db.get_nylas_grants_by_user(user_id)
        if not grants:
            raise HTTPException(status_code=400, detail="No email account connected. Please connect an email account via Nylas to send replies.")
        grant_id = grants[0]['grant_id']
    
    # Verify grant belongs to user
    grants = db.get_nylas_grants_by_user(user_id)
    grant = next((g for g in grants if g['grant_id'] == grant_id), None)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found or does not belong to user")
    
    # Ensure grant tokens are fresh
    grant_credentials = ensure_nylas_grant_tokens(grant_id)
    if not grant_credentials:
        raise HTTPException(status_code=500, detail="Failed to refresh grant tokens")
    
    # Extract recipient email from sender field
    sender_field = message['sender']
    # Try to extract email from "Name <email@domain.com>" or just "email@domain.com"
    email_match = re.search(r'<([^>]+)>', sender_field)
    if email_match:
        recipient_email = email_match.group(1)
    else:
        # Try to find email pattern directly
        email_match = re.search(r'[\w.-]+@[\w.-]+', sender_field)
        recipient_email = email_match.group(0) if email_match else sender_field
    
    # Build reply subject
    reply_subject = request.reply_subject or message['subject']
    if not reply_subject.startswith('Re:') and not reply_subject.startswith('RE:'):
        reply_subject = f"Re: {reply_subject}"
    
    try:
        # Send email via Nylas
        # Nylas v3 API uses messages.send() method
        send_response = nylas_client.messages.send(
            grant_id,
            request_body={
                "to": [{"email": recipient_email}],
                "subject": reply_subject,
                "body": request.reply_body,
                "reply_to_message_id": message.get('provider_message_id'),  # Link as reply if we have the original message ID
            }
        )
        
        # Mark message as replied
        db.mark_message_replied(message_id, user_id)
        
        return {
            "success": True,
            "message": "Reply sent successfully",
            "sent_message_id": getattr(send_response, 'id', None) if hasattr(send_response, 'id') else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {str(e)}")
