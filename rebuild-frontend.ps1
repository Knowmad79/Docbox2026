# Rebuild Frontend
# Usage: .\rebuild-frontend.ps1

Write-Host "Rebuilding DocboxRx Frontend..." -ForegroundColor Cyan

# Check if npm is installed
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: npm not found. Please install Node.js first." -ForegroundColor Red
    Write-Host "   Install: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Check if we're in the right directory
if (-not (Test-Path "docboxrx-frontend\package.json")) {
    Write-Host "ERROR: package.json not found. Make sure you are in the Docbox root directory." -ForegroundColor Red
    exit 1
}

# Navigate to frontend directory
Set-Location docboxrx-frontend

Write-Host "Installing dependencies (if needed)..." -ForegroundColor Yellow
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: npm install failed!" -ForegroundColor Red
    Set-Location ..
    exit 1
}

Write-Host ""
Write-Host "Building frontend..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS: Frontend built successfully!" -ForegroundColor Green
    
    # Check if dist folder exists
    if (Test-Path "dist") {
        $distSize = (Get-ChildItem -Path dist -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "Build output: dist/ folder ($([math]::Round($distSize, 2)) MB)" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "   1. Upload the dist folder to your web server" -ForegroundColor White
        Write-Host "   2. Make sure the server serves index.html for all routes" -ForegroundColor White
        Write-Host "   3. Test the app at your deployed URL" -ForegroundColor White
    } else {
        Write-Host "WARNING: dist folder not found after build" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    Set-Location ..
    exit 1
}

# Return to root directory
Set-Location ..

Write-Host ""
Write-Host "Rebuild complete!" -ForegroundColor Green
