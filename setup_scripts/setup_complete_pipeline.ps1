# WNBA Prediction Engine - Complete Setup Script
# PowerShell Version

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WNBA Prediction Engine - Complete Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ and try again" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if git is installed
try {
    $gitVersion = git --version 2>&1
    Write-Host "Git found: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Git is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Git and try again" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 1: Creating project directory..." -ForegroundColor Yellow

if (-not (Test-Path "wnba-prediction-engine")) {
    New-Item -ItemType Directory -Name "wnba-prediction-engine" | Out-Null
    Set-Location "wnba-prediction-engine"
    Write-Host "Cloning repository from GitHub..." -ForegroundColor Green
    git clone https://github.com/gallagjj/wnba-prediction-engine.git .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to clone repository" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Set-Location "wnba-prediction-engine"
    Write-Host "Repository already exists, updating..." -ForegroundColor Green
    git pull
}

Write-Host ""
Write-Host "Step 2: Creating virtual environment..." -ForegroundColor Yellow

if (Test-Path "venv") {
    Write-Host "Virtual environment already exists, removing..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "venv"
}

python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 3: Activating virtual environment and installing dependencies..." -ForegroundColor Yellow

& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Installing required packages..." -ForegroundColor Green
pip install --upgrade pip
pip install -r setup_scripts/requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 4: Creating data directories..." -ForegroundColor Yellow

@("data", "data\raw", "data\processed", "data\features", "models", "plots") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Name $_ | Out-Null
    }
}

Write-Host ""
Write-Host "Step 5: Running data acquisition scripts..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Running: fetch_wnba_boxscores.py" -ForegroundColor Green
python scripts\01_acquisition\fetch_wnba_boxscores.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to fetch boxscores" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Running: fetch_wnba_playbyplay.py" -ForegroundColor Green
python scripts\01_acquisition\fetch_wnba_playbyplay.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to fetch play-by-play data" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Running: fetch_wnba_team_gamelog.py" -ForegroundColor Green
python scripts\01_acquisition\fetch_wnba_team_gamelog.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to fetch team gamelogs" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 6: Running data validation scripts..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Running: validate_data_completeness.py" -ForegroundColor Green
python scripts\01_acquisition\validate_data_completeness.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Data validation failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Running: check_pbp_coverage.py" -ForegroundColor Green
python scripts\01_acquisition\check_pbp_coverage.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Play-by-play coverage check failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 7: Running data processing scripts..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Running: add_misc_stats.py" -ForegroundColor Green
python scripts\02_processing\add_misc_stats.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to add miscellaneous stats" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Running: build_possession_based_features.py" -ForegroundColor Green
python scripts\02_processing\build_possession_based_features.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build possession-based features" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Running: validate_on_court_counts.py" -ForegroundColor Green
python scripts\02_processing\validate_on_court_counts.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: On-court validation failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your WNBA Prediction Engine is now ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Data files created:" -ForegroundColor Yellow
Write-Host "- Raw boxscores, play-by-play, and team gamelogs in data\raw\" -ForegroundColor White
Write-Host "- Processed data with misc stats in data\processed\" -ForegroundColor White
Write-Host "- Possession-based player features in data\features\" -ForegroundColor White
Write-Host ""
Write-Host "To activate the environment in the future:" -ForegroundColor Yellow
Write-Host "  cd wnba-prediction-engine" -ForegroundColor White
Write-Host "  venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To run individual scripts:" -ForegroundColor Yellow
Write-Host "  python scripts\01_acquisition\script_name.py" -ForegroundColor White
Write-Host "  python scripts\02_processing\script_name.py" -ForegroundColor White
Write-Host ""

Read-Host "Press Enter to exit" 