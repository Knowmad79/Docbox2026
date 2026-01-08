# Connection Troubleshooting - "Failed to Fetch" Error

## 🔍 Problem
Login/registration shows "Failed to fetch" - cannot connect to backend.

## ✅ Fixes Applied

### 1. **Backend Health Check**
- Added `/health` endpoint
- Frontend tests connection on load
- Shows warning if backend unreachable

### 2. **Better Error Messages**
- Detailed error messages
- Shows exact URL being called
- Lists possible causes

### 3. **CORS Configuration**
- Explicit CORS methods
- Expose headers
- Allow all origins

### 4. **Connection Testing**
- Frontend tests backend on page load
- Console logs connection status
- Clear error messages

---

## 🧪 Testing Steps

### Step 1: Check Backend is Running
```bash
# Visit in browser:
https://app-nkizyevt.fly.dev/health

# Should return:
{"status": "healthy", "service": "DocBoxRX API"}
```

### Step 2: Check Browser Console
1. Open browser (F12)
2. Go to Console tab
3. Look for:
   - `API_URL: https://app-nkizyevt.fly.dev`
   - `✅ Backend connection successful` or `❌ Backend connection failed`

### Step 3: Check Network Tab
1. Open browser (F12)
2. Go to Network tab
3. Try to login
4. Look for:
   - Request to `https://app-nkizyevt.fly.dev/api/auth/login`
   - Status code (200 = success, 404 = not found, etc.)
   - CORS errors (red)

---

## 🐛 Common Issues

### Issue 1: Backend Not Running
**Symptoms:**
- "Failed to fetch" error
- Network tab shows "Failed" or "CORS error"

**Fix:**
```bash
# Check Fly.io status
flyctl status --app app-nkizyevt

# Restart if needed
flyctl restart --app app-nkizyevt

# Or redeploy
cd docboxrx-backend
flyctl deploy
```

### Issue 2: CORS Error
**Symptoms:**
- Browser console shows CORS error
- Network tab shows OPTIONS request failed

**Fix:**
- Backend CORS is configured correctly
- Check if backend is actually running
- Verify `allow_origins=["*"]` in main.py

### Issue 3: Wrong API URL
**Symptoms:**
- Console shows wrong URL
- Requests going to localhost instead of Fly.io

**Fix:**
- Check console: `API_URL: https://app-nkizyevt.fly.dev`
- If wrong, set environment variable:
  ```bash
  # In frontend .env file:
  VITE_API_URL=https://app-nkizyevt.fly.dev
  ```

### Issue 4: Network/Firewall
**Symptoms:**
- Can't reach backend at all
- Timeout errors

**Fix:**
- Check internet connection
- Check firewall settings
- Try from different network
- Test backend directly: `curl https://app-nkizyevt.fly.dev/health`

---

## 🔧 Quick Fixes

### Fix 1: Rebuild Frontend
```bash
cd docboxrx-frontend
npm run build
# Upload dist/ folder
```

### Fix 2: Restart Backend
```bash
flyctl restart --app app-nkizyevt
```

### Fix 3: Check Backend Logs
```bash
flyctl logs --app app-nkizyevt
```

Look for:
- Server startup messages
- Error messages
- Connection issues

### Fix 4: Test Backend Directly
```bash
# Test health endpoint
curl https://app-nkizyevt.fly.dev/health

# Test login endpoint (should return 422 - missing data, but proves it's working)
curl -X POST https://app-nkizyevt.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 📊 Diagnostic Checklist

- [ ] Backend health check works: `https://app-nkizyevt.fly.dev/health`
- [ ] Console shows correct API_URL
- [ ] Console shows connection test result
- [ ] Network tab shows requests being made
- [ ] No CORS errors in console
- [ ] Backend logs show requests arriving
- [ ] Frontend is using correct URL

---

## 🚨 If Still Not Working

1. **Share these details:**
   - Browser console output (F12 → Console)
   - Network tab screenshot (F12 → Network)
   - Backend logs: `flyctl logs --app app-nkizyevt`
   - What API_URL shows in console

2. **Test backend directly:**
   ```bash
   curl https://app-nkizyevt.fly.dev/health
   curl https://app-nkizyevt.fly.dev/
   ```

3. **Check Fly.io status:**
   ```bash
   flyctl status --app app-nkizyevt
   flyctl logs --app app-nkizyevt
   ```

---

## ✅ Success Indicators

After fixes, you should see:
- ✅ Console: `API_URL: https://app-nkizyevt.fly.dev`
- ✅ Console: `✅ Backend connection successful`
- ✅ Network tab: Requests to backend succeed
- ✅ Login/registration works
- ✅ No CORS errors

---

## 📝 Next Steps

1. **Deploy backend with health check:**
   ```bash
   cd docboxrx-backend
   flyctl deploy
   ```

2. **Rebuild frontend:**
   ```bash
   cd docboxrx-frontend
   npm run build
   # Upload dist/ folder
   ```

3. **Test connection:**
   - Open browser console
   - Check for connection test
   - Try login/registration
