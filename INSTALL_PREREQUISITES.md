# Installing Prerequisites for DocboxRx Deployment

## Required Tools

### 1. Fly.io CLI (for backend deployment)

**Install via winget (recommended):**
```powershell
winget install flyctl
```

**Or download manually:**
- Visit: https://fly.io/docs/getting-started/installing-flyctl/
- Download the Windows installer
- Run the installer

**Verify installation:**
```powershell
flyctl version
```

**Login to Fly.io:**
```powershell
flyctl auth login
```

---

### 2. Node.js and npm (for frontend build)

**Install via winget (recommended):**
```powershell
winget install OpenJS.NodeJS
```

**Or download manually:**
- Visit: https://nodejs.org/
- Download the LTS version (recommended)
- Run the installer

**Verify installation:**
```powershell
node --version
npm --version
```

---

## Quick Install (All at Once)

Run these commands in PowerShell:

```powershell
# Install Fly.io CLI
winget install flyctl

# Install Node.js
winget install OpenJS.NodeJS

# Verify installations
flyctl version
node --version
npm --version
```

---

## After Installation

1. **Restart PowerShell** (to refresh PATH)
2. **Check prerequisites:**
   ```powershell
   .\check-prerequisites.ps1
   ```
3. **Deploy:**
   ```powershell
   .\deploy-all.ps1
   ```

---

## Troubleshooting

### flyctl not found after installation
- Restart PowerShell
- Check PATH: `$env:PATH`
- Try: `refreshenv` (if using Chocolatey)

### npm not found after installation
- Restart PowerShell
- Verify Node.js installation: `where.exe node`
- Reinstall Node.js if needed

### Permission errors
- Run PowerShell as Administrator
- Check UAC settings

---

## Alternative: Manual Deployment

If you prefer not to install tools:

### Backend Deployment
1. Use Fly.io web dashboard
2. Or use Docker with Fly.io

### Frontend Build
1. Use online build services
2. Or build on a different machine with Node.js

---

## Next Steps

Once prerequisites are installed:
1. Run `.\check-prerequisites.ps1` to verify
2. Run `.\deploy-all.ps1` to deploy everything
3. Upload `docboxrx-frontend\dist\` to your web server
