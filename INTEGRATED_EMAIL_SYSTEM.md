# Integrated Email System - Architecture

## 🎯 Goal: Professional Email System

Build a **jukebox-style email repository** - fast access, metadata-indexed, no file storage overhead. Like a jukebox accesses records by index, we access emails by metadata.

---

## 🏗️ Architecture

### 1. **Email Repository (Jukebox System)**

```
┌─────────────────────────────────────┐
│   Email Metadata Index (Fast)        │
│   - ID, sender, subject, date        │
│   - Zone, confidence, thread_id      │
│   - Provider message ID (pointer)    │
└─────────────────────────────────────┘
              ↓ (on-demand)
┌─────────────────────────────────────┐
│   Full Content Cache (Lazy Load)    │
│   - raw_body (plain text)           │
│   - raw_body_html (formatted)       │
│   - Fetched from provider when needed│
└─────────────────────────────────────┘
```

**Key Principles:**
- ✅ Metadata always loaded (fast list view)
- ✅ Full content fetched on-demand (jukebox access)
- ✅ Cached after first access (no re-fetch)
- ✅ No file storage - just database fields

### 2. **Integrated Reply Composer**

**Current Flow (Too Long):**
```
Click Reply → Open Email Client → Compose → Send → Back to App
```

**New Flow (Integrated):**
```
Click Reply → Inline Composer Opens → Edit → Send → Done (stays in app)
```

---

## 📋 Implementation Status

### ✅ Completed
- [x] Full email content fetching from Nylas
- [x] Database schema for raw_body and raw_body_html
- [x] On-demand full content endpoint (`/api/messages/{id}/full`)
- [x] Jukebox-style caching (fetch once, cache forever)

### 🚧 In Progress
- [ ] Integrated inline reply composer UI
- [ ] Email thread/conversation view
- [ ] HTML email rendering
- [ ] Attachment support

---

## 🔧 API Endpoints

### Get Full Email Content (Jukebox Access)
```http
GET /api/messages/{message_id}/full
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "msg-123",
  "raw_body": "Full plain text email content...",
  "raw_body_html": "<html>Full HTML email content...</html>",
  "cached": true
}
```

**Behavior:**
- If cached: Returns immediately
- If not cached: Fetches from provider, caches, then returns

### Send Reply (Integrated)
```http
POST /api/messages/{message_id}/send-reply
Authorization: Bearer {token}
Content-Type: application/json

{
  "reply_body": "Your reply text here",
  "reply_subject": "Re: Original Subject" // Optional
}
```

---

## 🎨 Frontend Components Needed

### 1. **Full Email Viewer**
- Display raw_body or raw_body_html
- HTML rendering with sanitization
- Scrollable, professional layout
- Print-friendly

### 2. **Inline Reply Composer**
- Opens in modal/sidebar
- Pre-filled with draft reply
- Editable text area
- Send button (one click)
- Shows original email context

### 3. **Email Thread View**
- Show conversation history
- Group by thread_id
- Chronological order
- Reply inline to any message

---

## 🚀 Next Steps

1. **Update Frontend to Fetch Full Content**
   - Call `/api/messages/{id}/full` when email selected
   - Display full content (HTML if available)
   - Show loading state while fetching

2. **Build Inline Reply Composer**
   - Modal component
   - Pre-fill with draft_reply
   - Send via `/api/messages/{id}/send-reply`
   - Update UI after send

3. **Add Email Threading**
   - Group messages by thread_id
   - Show conversation view
   - Reply to specific message in thread

4. **Performance Optimization**
   - Lazy load full content
   - Cache HTML rendering
   - Virtual scrolling for long emails

---

## 💡 Jukebox Metaphor

**Like a Jukebox:**
- **Index (Metadata)**: Fast access to all emails
- **Records (Full Content)**: Fetched on-demand when selected
- **Caching**: Once played, stays in memory
- **No File Storage**: Just pointers to provider

**Benefits:**
- ⚡ Fast list view (metadata only)
- 💾 Efficient storage (no duplicate files)
- 🔄 Always fresh (can re-fetch from provider)
- 📦 Scalable (metadata is small, content is lazy)

---

## 📝 Database Schema

```sql
messages (
  id, user_id, sender, subject, snippet,
  raw_body TEXT,        -- Full plain text (cached)
  raw_body_html TEXT,   -- Full HTML (cached)
  provider_message_id,  -- Pointer to provider
  provider_thread_id,   -- For threading
  ...
)
```

**Indexes for Fast Access:**
- `idx_messages_user_id` - Fast user queries
- `idx_messages_provider_message_id` - Fast provider lookups
- `idx_messages_thread_id` - Fast threading

---

## 🎯 Success Criteria

- ✅ Click email → Full content loads instantly (if cached) or within 2 seconds (if fetching)
- ✅ Click Reply → Composer opens inline, one click to send
- ✅ No external email client needed
- ✅ Professional email reading experience
- ✅ Fast, scalable, future-proof
