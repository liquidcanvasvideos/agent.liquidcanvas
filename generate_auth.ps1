# PowerShell script to generate authentication credentials
# Run this script to automatically set up authentication

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Authentication Credentials Generator" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available (try py first, then python)
$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python first, or run generate_auth.py manually" -ForegroundColor Yellow
    exit 1
}

# Run the Python script
Write-Host "Running credential generator..." -ForegroundColor Green
if (Get-Command py -ErrorAction SilentlyContinue) {
    py generate_auth.py
} else {
    python generate_auth.py
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Authentication credentials generated successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Restart your backend server" -ForegroundColor White
    Write-Host "2. Visit https://agent.liquidcanvas.art/login" -ForegroundColor White
    Write-Host "   (For local dev: http://localhost:3000/login)" -ForegroundColor Gray
    Write-Host "3. Use the generated credentials to log in" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Error generating credentials" -ForegroundColor Red
    Write-Host "Please check the error message above" -ForegroundColor Yellow
}

