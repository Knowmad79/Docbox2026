# DocBoxRX Deployment Guide

## 🌐 Your Live URLs

- **Frontend (Website):** https://full-stack-apps-ah1tro24.devinapps.com
- **Backend API:** https://app-nkizyevt.fly.dev
- **Health Check:** https://app-nkizyevt.fly.dev/healthz

---

## 📦 Step 1: Deploy Backend (Fly.io)

The backend is hosted on Fly.io. To update it:

### Prerequisites
1. Install Fly.io CLI: https://fly.io/docs/hands-on/install-flyctl/
2. Login: `flyctl auth login`

### Deploy Backend

```bash
# Navigate to backend directory
cd docboxrx-backend

# Deploy to Fly.io
flyctl deploy

# Or if you need to set secrets (API keys, etc.)
flyctl secrets set NYLAS_API_KEY=your_key_here
flyctl secrets set CEREBRAS_API_KEY=your_key_here
```

### Check Backend Status

```bash
# View logs
flyctl logs

# Check app status
flyctl status

# SSH into the app (if needed)
flyctl ssh console
```

---

## 🎨 Step 2: Deploy Frontend

The frontend is hosted at `devinapps.com`. You need to:

### Option A: If you have SSH access to the server

```bash
# Navigate to frontend directory
cd docboxrx-frontend

# Build the frontend
npm run build

# This creates a 'dist' folder with the built files

# Copy dist folder to server (replace with your server details)
# Example using SCP:
scp -r dist/* user@server:/path/to/web/root/

# Or if you have direct server access:
# 1. SSH into server: ssh user@server
# 2. Navigate to: /home/ubuntu/docboxrx/docboxrx-frontend/
# 3. Run: npm run build
# 4. Copy dist/* to web server directory
```

### Option B: If using a deployment service

1. **Build locally:**
   ```bash
   cd docboxrx-frontend
   npm install
   npm run build
   ```

2. **Upload the `dist/` folder** to your hosting service:
   - The `dist/` folder contains all the built files
   - Upload everything inside `dist/` to your web server root

### Option C: Manual Build & Deploy

```bash
# 1. Build the frontend
cd docboxrx-frontend
npm install
npm run build

# 2. The dist/ folder now contains:
#    - index.html
#    - assets/ (CSS and JS files)
#    - vite.svg

# 3. Upload these files to your web hosting:
#    - If using FTP: Upload dist/* to web root
#    - If using cPanel: Upload dist/* to public_html
#    - If using a VPS: Copy dist/* to /var/www/html or similar
```

---

## 🔍 How to Check Your Website

### 1. **Frontend (Main Website)**
   - URL: https://full-stack-apps-ah1tro24.devinapps.com
   - This is where users interact with the app
   - Check if changes are visible after deployment

### 2. **Backend API**
   - URL: https://app-nkizyevt.fly.dev
   - Health check: https://app-nkizyevt.fly.dev/healthz
   - API docs: https://app-nkizyevt.fly.dev/docs (if enabled)

### 3. **Test the Updates**

After deploying, test:
- ✅ Login/Register works
- ✅ Emails display full content (not truncated)
- ✅ "Send Reply" button sends emails
- ✅ Nylas sync works
- ✅ CloudMailin webhook receives emails

---

## 🚀 Quick Deploy Commands

### Backend (Fly.io)
```bash
cd docboxrx-backend
flyctl deploy
```

### Frontend (Build)
```bash
cd docboxrx-frontend
npm run build
# Then upload dist/ folder to your web server
```

---

## 🔧 Troubleshooting

### Backend not updating?
- Check Fly.io logs: `flyctl logs`
- Verify deployment succeeded: `flyctl status`
- Check if environment variables are set: `flyctl secrets list`

### Frontend not updating?
- Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
- Check browser console for errors (F12)
- Verify `dist/` folder was uploaded correctly
- Check web server is serving the new files

### API connection issues?
- Verify `VITE_API_URL` in frontend points to: `https://app-nkizyevt.fly.dev`
- Check CORS is enabled in backend (should be `allow_origins=["*"]`)
- Test backend directly: `curl https://app-nkizyevt.fly.dev/healthz`

---

## 📝 Environment Variables

### Backend (Fly.io)
Set these via: `flyctl secrets set KEY=value`

```
DATABASE_URL=postgresql://...
CEREBRAS_API_KEY=...
NYLAS_API_KEY=...
NYLAS_CLIENT_ID=...
JWT_SECRET=...
```

### Frontend
Create `.env` file in `docboxrx-frontend/`:
```
VITE_API_URL=https://app-nkizyevt.fly.dev
```

---

## 🎯 What Changed in This Update

1. ✅ Removed all 500-character truncations
2. ✅ Full email content now stored and displayed
3. ✅ Added "Send Reply" functionality via Nylas
4. ✅ Added `raw_body` field to database
5. ✅ Frontend shows full email content

After deploying, **new emails** will have full content. Old emails that were truncated before will still be truncated (they were saved that way).

---

## 📞 Need Help?

- **Fly.io Docs:** https://fly.io/docs/
- **Vite Build Docs:** https://vitejs.dev/guide/build.html
- **Check logs:** `flyctl logs` for backend issues
