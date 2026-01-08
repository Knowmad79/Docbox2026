# Deploy All - Backend + Frontend
# Usage: .\deploy-all.ps1

Write-Host "🚀 Deploying DocboxRx - Full System" -ForegroundColor Cyan
Write-Host "="*50 -ForegroundColor Cyan

# Step 1: Deploy Backend (if flyctl is available)
Write-Host "`n[Step 1/3] Deploying Backend..." -ForegroundColor Yellow

if (Get-Command flyctl -ErrorAction SilentlyContinue) {
    & .\deploy-backend.ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n⚠️  Backend deployment failed, but continuing with frontend..." -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  flyctl not found. Skipping backend deployment." -ForegroundColor Yellow
    Write-Host "   To deploy backend, install Fly.io CLI:" -ForegroundColor White
    Write-Host "   https://fly.io/docs/getting-started/installing-flyctl/" -ForegroundColor Cyan
    Write-Host "   Or use: winget install flyctl" -ForegroundColor Cyan
}

# Step 2: Rebuild Frontend
Write-Host "`n[Step 2/3] Rebuilding Frontend..." -ForegroundColor Yellow
& .\rebuild-frontend.ps1

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Frontend rebuild failed. Stopping." -ForegroundColor Red
    exit 1
}

# Step 3: Test System
Write-Host "`n[Step 3/3] Testing System..." -ForegroundColor Yellow
Start-Sleep -Seconds 5  # Give backend time to fully start
& .\test-system.ps1

Write-Host "`n" + "="*50 -ForegroundColor Cyan
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "="*50 -ForegroundColor Cyan

Write-Host "`n📋 Summary:" -ForegroundColor Yellow
Write-Host "   Backend: https://app-nkizyevt.fly.dev" -ForegroundColor Cyan
Write-Host "   Frontend: Built in docboxrx-frontend\dist\" -ForegroundColor Cyan
Write-Host "`n📤 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Upload dist/ folder to your web server" -ForegroundColor White
Write-Host "   2. Test login in the app" -ForegroundColor White
Write-Host "   3. Verify full email content loads" -ForegroundColor White
Write-Host "   4. Test inline reply functionality" -ForegroundColor White
