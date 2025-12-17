# Run pipeline status fields migration
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Running Database Migration" -ForegroundColor Green
Write-Host "  Pipeline Status Fields" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Find Python executable
$pythonExe = $null
if (Test-Path "..\venv\Scripts\python.exe") {
    $pythonExe = "..\venv\Scripts\python.exe"
    Write-Host "Using Python from: ..\venv\Scripts\python.exe" -ForegroundColor Green
} elseif (Test-Path "venv\Scripts\python.exe") {
    $pythonExe = "venv\Scripts\python.exe"
    Write-Host "Using Python from: venv\Scripts\python.exe" -ForegroundColor Green
} else {
    # Try common Python installations
    $pythonPaths = @(
        "python3",
        "py",
        "python"
    )
    foreach ($path in $pythonPaths) {
        try {
            $result = & $path --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pythonExe = $path
                Write-Host "Using Python from: $path" -ForegroundColor Green
                break
            }
        } catch {
            continue
        }
    }
    
    if (-not $pythonExe) {
        Write-Host "ERROR: Python not found!" -ForegroundColor Red
        Write-Host "Please install Python or activate your virtual environment" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "The migration will run automatically when you start the backend server." -ForegroundColor Cyan
        exit 1
    }
}

Write-Host ""
Write-Host "Running migration: alembic upgrade head" -ForegroundColor Yellow
Write-Host ""

# Run the migration
try {
    & $pythonExe -m alembic upgrade head
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ Migration completed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "The following columns have been added to the 'prospects' table:" -ForegroundColor Cyan
        Write-Host "  - discovery_status" -ForegroundColor White
        Write-Host "  - approval_status" -ForegroundColor White
        Write-Host "  - scrape_status" -ForegroundColor White
        Write-Host "  - verification_status" -ForegroundColor White
        Write-Host "  - draft_status" -ForegroundColor White
        Write-Host "  - send_status" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "⚠️  Migration may have already been applied or encountered an issue." -ForegroundColor Yellow
        Write-Host "Check the output above for details." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Note: The migration will also run automatically when you start the backend." -ForegroundColor Cyan
    }
} catch {
    Write-Host ""
    Write-Host "❌ Error running migration: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "The migration will run automatically when you start the backend server." -ForegroundColor Cyan
    exit 1
}

