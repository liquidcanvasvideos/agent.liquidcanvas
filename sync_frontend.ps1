# Script to sync frontend code from monorepo to separate agent-frontend repository

Write-Host "=== Frontend Sync Script ===" -ForegroundColor Cyan
Write-Host ""

# Set paths
$monorepoFrontend = "C:\Users\MIKENZY\Documents\Apps\liquidcanvas\frontend"
$separateRepo = "C:\Users\MIKENZY\Documents\Apps\agent-frontend"

# Check if monorepo frontend exists
if (-not (Test-Path $monorepoFrontend)) {
    Write-Host "ERROR: Monorepo frontend not found at: $monorepoFrontend" -ForegroundColor Red
    exit 1
}

# Check if separate repo exists
if (-not (Test-Path $separateRepo)) {
    Write-Host "Separate repo not found. Cloning..." -ForegroundColor Yellow
    $parentDir = Split-Path $separateRepo -Parent
    Set-Location $parentDir
    git clone https://github.com/Jim-devENG/agent-frontend.git
    if (-not (Test-Path $separateRepo)) {
        Write-Host "ERROR: Failed to clone repository" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Copying files from monorepo to separate repo..." -ForegroundColor Green
Write-Host "Source: $monorepoFrontend" -ForegroundColor Gray
Write-Host "Destination: $separateRepo" -ForegroundColor Gray
Write-Host ""

# Remove existing directories first to prevent nesting
Write-Host "Cleaning existing directories..." -ForegroundColor Yellow
if (Test-Path "$separateRepo\app") { Remove-Item -Path "$separateRepo\app" -Recurse -Force }
if (Test-Path "$separateRepo\components") { Remove-Item -Path "$separateRepo\components" -Recurse -Force }
if (Test-Path "$separateRepo\lib") { Remove-Item -Path "$separateRepo\lib" -Recurse -Force }

# Copy directories
Write-Host "Copying app/..." -ForegroundColor Yellow
Copy-Item -Path "$monorepoFrontend\app" -Destination "$separateRepo\app" -Recurse -Force

Write-Host "Copying components/..." -ForegroundColor Yellow
Copy-Item -Path "$monorepoFrontend\components" -Destination "$separateRepo\components" -Recurse -Force

Write-Host "Copying lib/..." -ForegroundColor Yellow
Copy-Item -Path "$monorepoFrontend\lib" -Destination "$separateRepo\lib" -Recurse -Force

# Copy config files
Write-Host "Copying config files..." -ForegroundColor Yellow
Copy-Item -Path "$monorepoFrontend\package.json" -Destination "$separateRepo\package.json" -Force
Copy-Item -Path "$monorepoFrontend\tsconfig.json" -Destination "$separateRepo\tsconfig.json" -Force
Copy-Item -Path "$monorepoFrontend\tailwind.config.js" -Destination "$separateRepo\tailwind.config.js" -Force
Copy-Item -Path "$monorepoFrontend\postcss.config.js" -Destination "$separateRepo\postcss.config.js" -Force
Copy-Item -Path "$monorepoFrontend\next.config.js" -Destination "$separateRepo\next.config.js" -Force

# Copy .gitignore if it exists
if (Test-Path "$monorepoFrontend\.gitignore") {
    Copy-Item -Path "$monorepoFrontend\.gitignore" -Destination "$separateRepo\.gitignore" -Force
    Write-Host "Copied .gitignore" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Files copied successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. cd $separateRepo" -ForegroundColor White
Write-Host "2. git add ." -ForegroundColor White
Write-Host "3. git commit -m 'Update frontend to use new backend API endpoints'" -ForegroundColor White
Write-Host "4. git push origin main" -ForegroundColor White
Write-Host ""
Write-Host "Vercel will automatically redeploy after you push!" -ForegroundColor Green

