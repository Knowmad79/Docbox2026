# DOCBOX API CONTRACT
# Shared specification for all AI agents

## AUTHENTICATION ENDPOINTS

### POST /api/auth/register
Request: `{ email: string, password: string, name: string, practice_name?: string }`
Response: `{ 
  requires_verification: boolean,
  message: string,
  token?: string,
  user?: { id: string, email: string, name: string }
}`

### POST /api/auth/login
Request: `{ email: string, password: string }`
Response: `{ 
  token: string,
  user: { id: string, email: string, name: string, practice_name?: string }
}`

### GET /api/auth/me
Headers: `Authorization: Bearer {token}`
Response: `{ id: string, email: string, name: string, practice_name?: string }`

## NYLAS OAUTH ENDPOINTS

### GET /api/nylas/auth-url
Headers: `Authorization: Bearer {token}`
Query: `provider: "google" | "microsoft" | "yahoo" | "imap"`
Response: `{ auth_url: string, provider: string }`

### GET /api/nylas/auth-url-public
Query: `provider: "google" | "microsoft" | "yahoo" | "imap"`
Response: `{ auth_url: string, provider: string }`

### GET /api/nylas/callback
Query: `code: string, state: string`
Response: `Redirect to frontend with success/error params`

### GET /api/nylas/grants
Headers: `Authorization: Bearer {token}`
Response: `{ 
  grants: [{
    id: string,
    grant_id: string,
    email: string,
    provider: string,
    created_at: string,
    last_sync_at?: string,
    status?: "active" | "expired" | "error"
  }]
}`

### DELETE /api/nylas/disconnect/{grant_id}
Headers: `Authorization: Bearer {token}`
Response: `{ success: boolean }`

### POST /api/nylas/sync/{grant_id}
Headers: `Authorization: Bearer {token}`
Response: `{ 
  success: boolean,
  messages_synced: number,
  sync_time: string
}`

## MESSAGE ENDPOINTS

### GET /api/messages
Headers: `Authorization: Bearer {token}`
Query: `zone?: "STAT" | "TODAY" | "THIS_WEEK" | "LATER", search?: string`
Response: `{ 
  zones: {
    STAT: Message[],
    TODAY: Message[],
    THIS_WEEK: Message[],
    LATER: Message[]
  },
  total: number
}`

### GET /api/messages/{message_id}/full
Headers: `Authorization: Bearer {token}`
Response: `{ 
  id: string,
  raw_body?: string,
  raw_body_html?: string,
  cached: boolean
}`

### PATCH /api/messages/{message_id}/read
Headers: `Authorization: Bearer {token}`
Response: `{ success: boolean }`

### PATCH /api/messages/{message_id}/star
Headers: `Authorization: Bearer {token}`
Response: `{ success: boolean }`

### POST /api/messages/{message_id}/reply
Headers: `Authorization: Bearer {token}`
Request: `{ 
  content: string,
  tone?: "professional" | "casual" | "urgent" | "detailed"
}`
Response: `{ 
  success: boolean,
  message_id: string,
  sent_at: string
}`

### POST /api/messages/{message_id}/suggest-replies
Headers: `Authorization: Bearer {token}`
Request: `{ 
  tone: "professional" | "casual" | "urgent" | "detailed",
  context: "reply" | "forward"
}`
Response: `{ 
  suggestions: [{
    id: string,
    type: "professional" | "casual" | "urgent" | "detailed",
    title: string,
    content: string,
    tone: string
  }]
}`

## BRIEFING ENDPOINTS

### GET /api/briefing/daily-deck
Headers: `Authorization: Bearer {token}`
Query: `role?: string (default: "lead_doctor")`
Response: `MessageStateVector[]`

### POST /api/briefing/{vector_id}/action
Headers: `Authorization: Bearer {token}`
Request: `{ action: string }`
Response: `{ 
  success: boolean,
  action: string,
  vector_id: string
}`

## WEBHOOK ENDPOINTS

### POST /api/nylas/webhook
Headers: `X-Nylas-Signature: string`
Request: Nylas webhook payload
Response: `{ success: boolean }`

### GET /api/nylas/webhook
Query: `challenge: string`
Response: `{ challenge: string }`

## OPERATIONS ENDPOINTS

### GET /api/ops/diag
Headers: `Authorization: Bearer {token}`
Response: `{ 
  ok: boolean,
  uptime_seconds: number,
  db_ok: boolean,
  db_error?: string,
  nylas_configured: boolean,
  ai_configured: boolean,
  environment: string
}`

## DATA TYPES

### Message
```typescript
interface Message {
  id: string;
  user_id: string;
  sender: string;
  sender_domain: string;
  subject: string;
  snippet: string | null;
  zone: "STAT" | "TODAY" | "THIS_WEEK" | "LATER";
  confidence: number;
  reason: string;
  jone5_message: string;
  received_at: string;
  classified_at: string;
  corrected: boolean;
  corrected_at?: string;
  source_id?: string;
  source_name?: string;
  
  // Nylas integration
  grant_id?: string;
  provider_message_id?: string;
  thread_id?: string;
  provider?: string;
  
  // Full content
  raw_body?: string;
  raw_body_html?: string;
  raw_headers?: string;
  
  // Metadata
  metadata?: Record<string, any>;
  attachments?: Array<{
    id: string;
    filename: string;
    size: number;
    type: string;
  }>;
  has_attachments?: boolean;
  
  // Status
  status: "active" | "archived" | "deleted";
  read?: boolean;
  starred?: boolean;
  important?: boolean;
  
  // AI processing
  summary?: string;
  recommended_action?: string;
  action_type?: string;
  draft_reply?: string;
  llm_fallback?: boolean;
}
```

### MessageStateVector
```typescript
interface MessageStateVector {
  id: string;
  nylas_message_id: string;
  grant_id: string;
  intent_label: string;
  risk_score: number;
  context_blob: Record<string, any>;
  summary?: string;
  current_owner_role?: string;
  deadline_at?: string;
  lifecycle_state?: string;
  is_overdue?: boolean;
  created_at?: string;
  updated_at?: string;
}
```

## ERROR RESPONSES

All endpoints return consistent error format:
```json
{
  "detail": "Error description",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## STATUS CODES
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Validation Error
- 500: Server Error
