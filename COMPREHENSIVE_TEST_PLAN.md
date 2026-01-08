# Comprehensive Test Plan - DocboxRx Medical Email Triage

## 🎯 Core Requirements (Medical Professional First-Line Triage)

1. **Login Credentials** - Fast, reliable authentication
2. **Full Email Content** - Complete email body display (no truncation)
3. **Direct Inline Reply** - Reply without external email client routing
4. **Jukebox-Style Access** - Fast retrieval, cached when possible

---

## ✅ Test 1: Login Functionality

### Backend Test
```bash
# Test login endpoint
curl -X POST https://app-nkizyevt.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'

# Expected: 200 OK with token, OR 401 if wrong credentials
```

### Frontend Test
1. Open app
2. Enter credentials
3. Click Login
4. **Expected:** Instant login, no timeout, access to app

### Issues to Check
- [ ] No "Failed to fetch" errors
- [ ] No timeout errors
- [ ] Fast response (< 2 seconds)
- [ ] Token stored correctly
- [ ] User redirected to main app

---

## ✅ Test 2: Full Email Content Display

### Backend Test
```bash
# Test full content endpoint (requires auth token)
curl -X GET https://app-nkizyevt.fly.dev/api/messages/{message_id}/full \
  -H "Authorization: Bearer {token}"

# Expected: 
# {
#   "id": "...",
#   "raw_body": "Full email text...",
#   "raw_body_html": "<html>Full email HTML...</html>",
#   "cached": true/false
# }
```

### Frontend Test
1. Login to app
2. Click on any email in list
3. **Expected:** Full email content displays (not truncated snippet)

### Issues to Check
- [ ] Full email body shows (not just snippet)
- [ ] HTML emails render correctly
- [ ] Plain text emails show correctly
- [ ] No "Loading..." stuck state
- [ ] Content loads quickly (< 1 second if cached)

### Current Implementation Status
- ✅ Backend endpoint exists: `/api/messages/{message_id}/full`
- ✅ Database stores `raw_body` and `raw_body_html`
- ⚠️ **ISSUE:** Frontend may not be auto-loading full content on message select
- ⚠️ **NEEDS FIX:** Add useEffect to fetch full content when message selected

---

## ✅ Test 3: Direct Inline Reply (No External Routing)

### Backend Test
```bash
# Test reply endpoint (requires auth token)
curl -X POST https://app-nkizyevt.fly.dev/api/messages/{message_id}/send-reply \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "...",
    "reply_body": "Test reply",
    "reply_subject": "Re: Original Subject"
  }'

# Expected: 
# {
#   "success": true,
#   "message": "Reply sent successfully",
#   "sent_message_id": "..."
# }
```

### Frontend Test
1. Login to app
2. Click on an email
3. Click "Reply" button (or use draft reply)
4. **Expected:** Inline modal opens (NOT external email client)
5. Type reply
6. Click "Send Reply"
7. **Expected:** Reply sends directly via Nylas API, success message shows

### Issues to Check
- [ ] Reply modal opens inline (Dialog component)
- [ ] No external email client opens
- [ ] Reply sends via API (not mailto: link)
- [ ] Success message shows
- [ ] Message marked as replied
- [ ] No file location needed
- [ ] No routing to original email system

### Current Implementation Status
- ✅ Backend endpoint exists: `/api/messages/{message_id}/send-reply`
- ✅ Backend sends via Nylas API (not external routing)
- ✅ Frontend has inline reply modal (Dialog component)
- ✅ Frontend sends via API endpoint
- ✅ **CONFIRMED:** No external email client routing

---

## ✅ Test 4: Jukebox-Style Fast Access

### Test Caching
1. Open email first time → Should fetch from provider
2. Open same email again → Should load from cache instantly
3. **Expected:** Cached emails load < 100ms

### Test On-Demand Fetching
1. Open email without cached content
2. **Expected:** Fetches from provider automatically
3. **Expected:** Caches for future access

### Current Implementation Status
- ✅ Backend checks cache first
- ✅ Backend fetches on-demand if not cached
- ✅ Backend caches after fetch
- ✅ Fast access pattern implemented

---

## 🔧 Fixes Needed

### Fix 1: Auto-Load Full Email Content
**Issue:** Frontend doesn't automatically fetch full content when message selected.

**Fix:** Add useEffect to fetch `/api/messages/{message_id}/full` when `selectedMessage` changes.

**Location:** `docboxrx-frontend/src/App.tsx`

### Fix 2: Ensure Reply Button Visible
**Issue:** Need to verify "Reply" button is visible and accessible.

**Fix:** Check that reply button is in email detail view.

**Location:** `docboxrx-frontend/src/App.tsx` (around line 850)

---

## 🧪 End-to-End Test Flow

### Complete User Journey
1. **Login** → Should be instant, no errors
2. **View Email List** → Should load quickly
3. **Click Email** → Should show full content immediately
4. **Read Full Email** → Should see complete body, not snippet
5. **Click Reply** → Should open inline modal
6. **Type Reply** → Should work smoothly
7. **Send Reply** → Should send via API, show success
8. **No External Apps** → Should never open email client

---

## 📊 Success Criteria

### For Medical Professionals
- ✅ **Speed:** Login < 2 seconds
- ✅ **Completeness:** Full email content always visible
- ✅ **Convenience:** Reply without leaving app
- ✅ **Reliability:** No external dependencies for core functions
- ✅ **Efficiency:** Fast triage, quick decisions

### Technical
- ✅ All API endpoints respond correctly
- ✅ Frontend displays full content
- ✅ Reply sends via API (not external)
- ✅ Caching works for fast access
- ✅ No "Failed to fetch" errors
- ✅ No timeouts

---

## 🚨 Critical Issues to Fix

1. **Auto-load full email content** - Add useEffect hook
2. **Verify reply button visibility** - Ensure it's accessible
3. **Test end-to-end flow** - Complete user journey
4. **Deploy and verify** - Test on live deployment

---

## 📝 Test Results Template

```
Date: [DATE]
Tester: [NAME]

Login Test:
- [ ] Pass / [ ] Fail
- Notes: [NOTES]

Full Email Content Test:
- [ ] Pass / [ ] Fail
- Notes: [NOTES]

Inline Reply Test:
- [ ] Pass / [ ] Fail
- Notes: [NOTES]

Jukebox Access Test:
- [ ] Pass / [ ] Fail
- Notes: [NOTES]

Overall Status:
- [ ] Ready for Medical Professionals
- [ ] Needs Fixes
```
