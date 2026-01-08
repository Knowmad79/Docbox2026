# Deployment Scripts - DocboxRx

## 📋 Available Scripts

### 1. `deploy-backend.ps1`
Deploys the backend to Fly.io

**Usage:**
```powershell
.\deploy-backend.ps1
```

**What it does:**
- Checks for flyctl CLI
- Verifies fly.toml exists
- Deploys to Fly.io (app-nkizyevt)
- Tests backend health endpoint
- Reports deployment status

---

### 2. `rebuild-frontend.ps1`
Rebuilds the frontend production bundle

**Usage:**
```powershell
.\rebuild-frontend.ps1
```

**What it does:**
- Checks for npm
- Installs dependencies
- Builds production bundle
- Creates dist/ folder
- Reports build status

---

### 3. `test-system.ps1`
Tests the entire system

**Usage:**
```powershell
.\test-system.ps1
```

**What it tests:**
- Backend health endpoint
- Root endpoint
- Login endpoint (validation)
- CORS configuration
- Frontend build existence

**Output:**
- Pass/fail for each test
- Summary with total passed/failed

---

### 4. `deploy-all.ps1`
**Master script** - Deploys everything

**Usage:**
```powershell
.\deploy-all.ps1
```

**What it does:**
1. Deploys backend to Fly.io
2. Rebuilds frontend
3. Tests the system
4. Reports complete status

---

## 🚀 Quick Start

### Full Deployment (Recommended)
```powershell
.\deploy-all.ps1
```

### Individual Steps
```powershell
# Deploy backend only
.\deploy-backend.ps1

# Rebuild frontend only
.\rebuild-frontend.ps1

# Test system only
.\test-system.ps1
```

---

## 📝 Prerequisites

### For Backend Deployment
- [Fly.io CLI](https://fly.io/docs/getting-started/installing-flyctl/) installed
- Logged into Fly.io: `flyctl auth login`
- App configured: `app-nkizyevt`

### For Frontend Build
- [Node.js](https://nodejs.org/) installed (npm included)
- Dependencies installed: `npm install` (script does this)

---

## 🔧 Troubleshooting

### Backend Deployment Fails

**Error: flyctl not found**
```powershell
# Install Fly.io CLI
# Windows: Use winget or download from fly.io
winget install flyctl
```

**Error: Not authenticated**
```powershell
flyctl auth login
```

**Error: App not found**
```powershell
# Check app name in docboxrx-backend/fly.toml
# Or create new app:
cd docboxrx-backend
flyctl apps create app-nkizyevt
```

---

### Frontend Build Fails

**Error: npm not found**
```powershell
# Install Node.js from nodejs.org
# Or use winget:
winget install OpenJS.NodeJS
```

**Error: Dependencies fail**
```powershell
cd docboxrx-frontend
npm install --legacy-peer-deps
npm run build
```

---

### Tests Fail

**Backend not responding:**
- Wait 30-60 seconds after deployment
- Check Fly.io status: `flyctl status --app app-nkizyevt`
- Check logs: `flyctl logs --app app-nkizyevt`

**CORS errors:**
- Backend CORS is configured (`allow_origins=["*"]`)
- If still failing, check backend logs

---

## 📊 Expected Output

### Successful Deployment
```
🚀 Deploying DocboxRx Backend to Fly.io...
✅ Backend deployed successfully!
🌐 Backend URL: https://app-nkizyevt.fly.dev
✅ Backend health check passed!

🔨 Rebuilding DocboxRx Frontend...
✅ Frontend built successfully!
📁 Build output: dist/ folder (X.XX MB)

🧪 Testing DocboxRx System...
✅ All tests passed! System is ready.
```

---

## 🎯 Post-Deployment Checklist

After running `deploy-all.ps1`:

- [ ] Backend health check passes
- [ ] Frontend dist/ folder exists
- [ ] Upload dist/ to web server
- [ ] Test login in app
- [ ] Verify full email content loads
- [ ] Test inline reply functionality
- [ ] Check browser console for errors

---

## 🔄 Typical Workflow

1. **Make code changes**
2. **Run deployment:**
   ```powershell
   .\deploy-all.ps1
   ```
3. **Upload frontend:**
   - Upload `docboxrx-frontend/dist/` to web server
4. **Test:**
   - Test login
   - Test email viewing
   - Test reply functionality

---

## 📞 Support

If scripts fail:
1. Check error messages
2. Verify prerequisites
3. Check Fly.io status
4. Review backend logs: `flyctl logs --app app-nkizyevt`
5. Check frontend build output

---

## ✅ Success Indicators

**Backend:**
- ✅ `https://app-nkizyevt.fly.dev/health` returns 200
- ✅ `flyctl status` shows app running

**Frontend:**
- ✅ `dist/index.html` exists
- ✅ `dist/assets/` folder has JS/CSS files

**System:**
- ✅ All tests pass
- ✅ Login works in app
- ✅ Full email content displays
- ✅ Reply sends successfully
