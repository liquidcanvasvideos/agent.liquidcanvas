# PowerShell script to set up both Hunter.io and DataForSEO API credentials
# Run this script to configure both APIs in your .env file

$envFile = ".env"

# Check if .env exists
if (-not (Test-Path $envFile)) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    New-Item -ItemType File -Path $envFile | Out-Null
}

# Read existing .env content
$envContent = @()
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
}

# Hunter.io API Key
$hunterKey = "ba71410fc6c6dcec6df42333e933a40bdf2fa1cb"

# DataForSEO Credentials
$dataforseoLogin = "jeremiah@liquidcanvas.art"
$dataforseoPassword = "b85d55cf567939e7"

# Function to update or add environment variable
function Update-EnvVar {
    param(
        [string]$Key,
        [string]$Value
    )
    
    $found = $false
    $newContent = @()
    
    foreach ($line in $envContent) {
        if ($line -match "^$Key=") {
            $newContent += "$Key=$Value"
            $found = $true
            Write-Host "Updated: $Key" -ForegroundColor Green
        } else {
            $newContent += $line
        }
    }
    
    if (-not $found) {
        $newContent += "$Key=$Value"
        Write-Host "Added: $Key" -ForegroundColor Green
    }
    
    $script:envContent = $newContent
}

# Update or add API credentials
Write-Host "`nConfiguring API credentials..." -ForegroundColor Cyan
Update-EnvVar "HUNTER_IO_API_KEY" $hunterKey
Update-EnvVar "DATAFORSEO_LOGIN" $dataforseoLogin
Update-EnvVar "DATAFORSEO_PASSWORD" $dataforseoPassword

# Write back to .env file
$envContent | Set-Content $envFile

Write-Host "`n✅ API credentials configured successfully!" -ForegroundColor Green
Write-Host "`nConfigured APIs:" -ForegroundColor Cyan
Write-Host "  ✅ Hunter.io API Key: $($hunterKey.Substring(0, 10))..." -ForegroundColor Green
Write-Host "  ✅ DataForSEO Login: $dataforseoLogin" -ForegroundColor Green
Write-Host "  ✅ DataForSEO Password: $($dataforseoPassword.Substring(0, 10))..." -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Restart your backend server to load the new credentials" -ForegroundColor White
Write-Host "  2. The system will automatically use both APIs:" -ForegroundColor White
Write-Host "     - DataForSEO: For website discovery (better search results)" -ForegroundColor White
Write-Host "     - Hunter.io: For email extraction (after scraping)" -ForegroundColor White

