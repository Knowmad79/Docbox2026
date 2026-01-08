# Check Prerequisites for Deployment
# Usage: .\check-prerequisites.ps1

Write-Host "Checking Prerequisites for DocboxRx Deployment..." -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check Fly.io CLI
Write-Host "[1/2] Checking Fly.io CLI (flyctl)..." -ForegroundColor Yellow
if (Get-Command flyctl -ErrorAction SilentlyContinue) {
    $version = flyctl version 2>&1
    Write-Host "   OK: flyctl is installed" -ForegroundColor Green
    Write-Host "   Version: $version" -ForegroundColor Gray
} else {
    Write-Host "   MISSING: flyctl not found" -ForegroundColor Red
    Write-Host "   Install: https://fly.io/docs/getting-started/installing-flyctl/" -ForegroundColor Yellow
    Write-Host "   Or use: winget install flyctl" -ForegroundColor Yellow
    $allGood = $false
}

Write-Host ""

# Check Node.js/npm
Write-Host "[2/2] Checking Node.js and npm..." -ForegroundColor Yellow
if (Get-Command npm -ErrorAction SilentlyContinue) {
    $npmVersion = npm --version
    $nodeVersion = node --version
    Write-Host "   OK: npm is installed" -ForegroundColor Green
    Write-Host "   npm version: $npmVersion" -ForegroundColor Gray
    Write-Host "   node version: $nodeVersion" -ForegroundColor Gray
} else {
    Write-Host "   MISSING: npm not found" -ForegroundColor Red
    Write-Host "   Install: https://nodejs.org/" -ForegroundColor Yellow
    Write-Host "   Or use: winget install OpenJS.NodeJS" -ForegroundColor Yellow
    $allGood = $false
}

Write-Host ""
Write-Host "=" * 50 -ForegroundColor Cyan

if ($allGood) {
    Write-Host "SUCCESS: All prerequisites are installed!" -ForegroundColor Green
    Write-Host "You can now run: .\deploy-all.ps1" -ForegroundColor Cyan
} else {
    Write-Host "WARNING: Some prerequisites are missing." -ForegroundColor Yellow
    Write-Host "Please install the missing tools before deploying." -ForegroundColor Yellow
}
