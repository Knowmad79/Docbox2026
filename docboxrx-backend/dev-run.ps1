while ($true) {
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  Write-Output "uvicorn exited with code $LASTEXITCODE; restarting in 2s"
  Start-Sleep -Seconds 2
}
