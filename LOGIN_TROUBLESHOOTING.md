# Login Troubleshooting Guide

## ✅ Fixes Applied

### 1. **Email Verification Temporarily Disabled**
- Login now works even if email isn't verified
- Warning logged in console
- Can re-enable verification check if needed

### 2. **Better Error Messages**
- Frontend shows specific error messages
- Backend logs detailed errors
- Clear feedback for users

### 3. **Email Normalization**
- Email trimmed and lowercased
- Prevents whitespace issues

---

## 🔍 Common Login Issues

### Issue 1: "Invalid email or password"
**Causes:**
- Wrong email or password
- User doesn't exist in database
- Password hash mismatch

**Fix:**
- Check email spelling
- Verify user exists: `SELECT * FROM users WHERE email = '...'`
- Reset password if needed

### Issue 2: "Cannot connect to server"
**Causes:**
- Backend not running
- Wrong API_URL
- Network/CORS issues

**Fix:**
- Check backend is running: `flyctl status` or `python -m uvicorn app.main:app`
- Verify API_URL in frontend: `console.log(API_URL)`
- Check CORS settings

### Issue 3: "Request timed out"
**Causes:**
- Database connection slow
- Network latency
- Backend overloaded

**Fix:**
- Check database connection
- Increase timeout in frontend
- Check Fly.io logs: `flyctl logs`

### Issue 4: "Email not verified"
**Causes:**
- User registered but didn't verify email
- Verification link expired

**Fix:**
- Currently disabled (login works anyway)
- Can verify email later
- Or manually set `is_verified = 1` in database

---

## 🧪 Testing Login

### Test 1: Valid Credentials
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

**Expected:** Returns token and user data

### Test 2: Invalid Password
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "wrong"}'
```

**Expected:** 401 error "Invalid email or password"

### Test 3: Non-existent User
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "nonexistent@example.com", "password": "password123"}'
```

**Expected:** 401 error "Invalid email or password"

---

## 🔧 Debug Steps

### Step 1: Check Backend Logs
```bash
flyctl logs --app app-nkizyevt
```

Look for:
- "Login successful for user: ..."
- "Login failed: ..."
- Database connection errors

### Step 2: Check Database
```sql
SELECT id, email, is_verified FROM users WHERE email = 'your@email.com';
```

Verify:
- User exists
- Email matches (case-insensitive)
- Password hash is set

### Step 3: Check Frontend Console
Open browser DevTools (F12) → Console

Look for:
- API call errors
- Network errors
- Response status codes

### Step 4: Test API Directly
```bash
# Test login endpoint
curl -X POST https://app-nkizyevt.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}'
```

---

## 🐛 Common Fixes

### Fix 1: Database Connection
If login times out, check database:
```python
# In db.py, check connection pool
_pg_pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row, "connect_timeout": 5}
)
```

### Fix 2: Password Verification
If password always fails:
```python
# Check bcrypt is working
from app.main import verify_password, get_password_hash
hash = get_password_hash("test")
print(verify_password("test", hash))  # Should be True
```

### Fix 3: CORS Issues
If frontend can't call API:
```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## ✅ Success Indicators

After fixes, you should see:
- ✅ Login completes in < 2 seconds
- ✅ Token stored in localStorage
- ✅ User data loaded
- ✅ Messages fetch successfully
- ✅ No console errors

---

## 📝 Next Steps

If login still fails:
1. Share backend logs
2. Share browser console errors
3. Share network tab (F12 → Network)
4. Test API directly with curl
