# PowerShell script to add Hunter.io API key to .env file
$apiKey = "ba71410fc6c6dcec6df42333e933a40bdf2fa1cb"

Write-Host "Setting up Hunter.io API key..." -ForegroundColor Cyan

# Check if .env exists
if (Test-Path .env) {
    $content = Get-Content .env -Raw
    
    # Check if key already exists
    if ($content -match "HUNTER_IO_API_KEY") {
        Write-Host "⚠️  HUNTER_IO_API_KEY already exists in .env" -ForegroundColor Yellow
        Write-Host "Updating with new key..." -ForegroundColor Yellow
        
        # Remove old line and add new one
        $lines = Get-Content .env | Where-Object { $_ -notmatch "^HUNTER_IO_API_KEY" }
        $lines += "HUNTER_IO_API_KEY=$apiKey"
        $lines | Set-Content .env
    } else {
        Write-Host "✅ Adding HUNTER_IO_API_KEY to .env..." -ForegroundColor Green
        Add-Content .env "`nHUNTER_IO_API_KEY=$apiKey"
    }
} else {
    Write-Host "Creating .env file..." -ForegroundColor Green
    "HUNTER_IO_API_KEY=$apiKey" | Out-File .env -Encoding utf8
}

Write-Host ""
Write-Host "✅ Hunter.io API key configured!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart your backend server" -ForegroundColor White
Write-Host "2. The system will automatically use Hunter.io for email extraction" -ForegroundColor White
Write-Host "3. Check logs to see Hunter.io results" -ForegroundColor White

