# Deploy Backend to Fly.io
# Usage: .\deploy-backend.ps1

Write-Host "🚀 Deploying DocboxRx Backend to Fly.io..." -ForegroundColor Cyan

# Check if flyctl is installed
if (-not (Get-Command flyctl -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: flyctl not found. Please install Fly.io CLI first." -ForegroundColor Red
    Write-Host "   Install: https://fly.io/docs/getting-started/installing-flyctl/" -ForegroundColor Yellow
    exit 1
}

# Check if we're in the right directory
if (-not (Test-Path "docboxrx-backend\fly.toml")) {
    Write-Host "❌ Error: fly.toml not found. Make sure you're in the Docbox root directory." -ForegroundColor Red
    exit 1
}

# Navigate to backend directory
Set-Location docboxrx-backend

Write-Host "📦 Checking Fly.io status..." -ForegroundColor Yellow
flyctl status --app app-nkizyevt

Write-Host "`n🔨 Deploying backend..." -ForegroundColor Yellow
flyctl deploy --app app-nkizyevt

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Backend deployed successfully!" -ForegroundColor Green
    Write-Host "🌐 Backend URL: https://app-nkizyevt.fly.dev" -ForegroundColor Cyan
    
    Write-Host "`n🧪 Testing backend health..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    
    try {
        $response = Invoke-WebRequest -Uri "https://app-nkizyevt.fly.dev/health" -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Backend health check passed!" -ForegroundColor Green
            Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "⚠️  Health check failed (backend may still be starting): $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n❌ Deployment failed!" -ForegroundColor Red
    Set-Location ..
    exit 1
}

# Return to root directory
Set-Location ..

Write-Host "`n✅ Deployment complete!" -ForegroundColor Green
