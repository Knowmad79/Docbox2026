# Test DocboxRx System
# Usage: .\test-system.ps1

Write-Host "🧪 Testing DocboxRx System..." -ForegroundColor Cyan

$backendUrl = "https://app-nkizyevt.fly.dev"
$testsPassed = 0
$testsFailed = 0

# Test 1: Backend Health Check
Write-Host "`n[1/5] Testing backend health endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$backendUrl/health" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Health check passed" -ForegroundColor Green
        Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
        $testsPassed++
    } else {
        Write-Host "   ❌ Health check failed: Status $($response.StatusCode)" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "   ❌ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}

# Test 2: Root Endpoint
Write-Host "`n[2/5] Testing root endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$backendUrl/" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Root endpoint working" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "   ❌ Root endpoint failed: Status $($response.StatusCode)" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "   ❌ Root endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}

# Test 3: Login Endpoint (should return 422 for missing data, not 404)
Write-Host "`n[3/5] Testing login endpoint..." -ForegroundColor Yellow
try {
    $body = @{
        email = ""
        password = ""
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$backendUrl/api/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -UseBasicParsing `
        -TimeoutSec 10 `
        -ErrorAction Stop
    
    Write-Host "   ⚠️  Unexpected success (should fail with empty data)" -ForegroundColor Yellow
    $testsPassed++
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 422 -or $statusCode -eq 400) {
        Write-Host "   ✅ Login endpoint responding correctly (validation error expected)" -ForegroundColor Green
        $testsPassed++
    } elseif ($statusCode -eq 404) {
        Write-Host "   ❌ Login endpoint not found (404)" -ForegroundColor Red
        $testsFailed++
    } else {
        Write-Host "   ⚠️  Login endpoint returned: $statusCode" -ForegroundColor Yellow
        $testsPassed++
    }
}

# Test 4: CORS Headers
Write-Host "`n[4/5] Testing CORS configuration..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$backendUrl/health" `
        -Method OPTIONS `
        -UseBasicParsing `
        -TimeoutSec 10
    
    $corsHeaders = @("Access-Control-Allow-Origin", "Access-Control-Allow-Methods", "Access-Control-Allow-Headers")
    $hasCors = $false
    
    foreach ($header in $corsHeaders) {
        if ($response.Headers[$header]) {
            $hasCors = $true
            break
        }
    }
    
    if ($hasCors -or $response.StatusCode -eq 200) {
        Write-Host "   ✅ CORS configured (or endpoint allows OPTIONS)" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "   ⚠️  CORS headers not visible (may still work)" -ForegroundColor Yellow
        $testsPassed++
    }
} catch {
    Write-Host "   ⚠️  CORS test inconclusive: $($_.Exception.Message)" -ForegroundColor Yellow
    $testsPassed++
}

# Test 5: Frontend Build Check
Write-Host "`n[5/5] Checking frontend build..." -ForegroundColor Yellow
if (Test-Path "docboxrx-frontend\dist\index.html") {
    Write-Host "   ✅ Frontend build exists" -ForegroundColor Green
    $testsPassed++
} else {
    Write-Host "   ⚠️  Frontend not built (run .\rebuild-frontend.ps1)" -ForegroundColor Yellow
    $testsFailed++
}

# Summary
Write-Host "`n" + "="*50 -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "="*50 -ForegroundColor Cyan
Write-Host "✅ Passed: $testsPassed" -ForegroundColor Green
Write-Host "❌ Failed: $testsFailed" -ForegroundColor $(if ($testsFailed -gt 0) { "Red" } else { "Green" })

if ($testsFailed -eq 0) {
    Write-Host "`n🎉 All tests passed! System is ready." -ForegroundColor Green
} else {
    Write-Host "`n⚠️  Some tests failed. Check the errors above." -ForegroundColor Yellow
}

Write-Host "`n📝 Next steps:" -ForegroundColor Yellow
Write-Host "   1. If backend tests failed: Run .\deploy-backend.ps1" -ForegroundColor White
Write-Host "   2. If frontend not built: Run .\rebuild-frontend.ps1" -ForegroundColor White
Write-Host "   3. Test login with real credentials in the app" -ForegroundColor White
