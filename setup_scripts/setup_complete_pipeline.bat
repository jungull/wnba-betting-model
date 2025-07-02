@echo off
echo ========================================
echo WNBA Prediction Engine - Complete Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if git is installed
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in PATH
    echo Please install Git and try again
    pause
    exit /b 1
)

echo Step 1: Creating project directory...
if not exist "wnba-prediction-engine" (
    mkdir wnba-prediction-engine
    cd wnba-prediction-engine
    echo Cloning repository from GitHub...
    git clone https://github.com/gallagjj/wnba-prediction-engine.git .
    if errorlevel 1 (
        echo ERROR: Failed to clone repository
        pause
        exit /b 1
    )
) else (
    cd wnba-prediction-engine
    echo Repository already exists, updating...
    git pull
)

echo.
echo Step 2: Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists, removing...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo.
echo Step 3: Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Installing required packages...
pip install --upgrade pip
pip install -r setup_scripts/requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Step 4: Creating data directories...
if not exist "data" mkdir data
if not exist "data\raw" mkdir data\raw
if not exist "data\processed" mkdir data\processed
if not exist "data\features" mkdir data\features
if not exist "models" mkdir models
if not exist "plots" mkdir plots

echo.
echo Step 5: Running data acquisition scripts...
echo.
echo Running: fetch_wnba_boxscores.py
python scripts\01_acquisition\fetch_wnba_boxscores.py
if errorlevel 1 (
    echo ERROR: Failed to fetch boxscores
    pause
    exit /b 1
)

echo.
echo Running: fetch_wnba_playbyplay.py
python scripts\01_acquisition\fetch_wnba_playbyplay.py
if errorlevel 1 (
    echo ERROR: Failed to fetch play-by-play data
    pause
    exit /b 1
)

echo.
echo Running: fetch_wnba_team_gamelog.py
python scripts\01_acquisition\fetch_wnba_team_gamelog.py
if errorlevel 1 (
    echo ERROR: Failed to fetch team gamelogs
    pause
    exit /b 1
)

echo.
echo Step 6: Running data validation scripts...
echo.
echo Running: validate_data_completeness.py
python scripts\01_acquisition\validate_data_completeness.py
if errorlevel 1 (
    echo ERROR: Data validation failed
    pause
    exit /b 1
)

echo.
echo Running: check_pbp_coverage.py
python scripts\01_acquisition\check_pbp_coverage.py
if errorlevel 1 (
    echo ERROR: Play-by-play coverage check failed
    pause
    exit /b 1
)

echo.
echo Step 7: Running data processing scripts...
echo.
echo Running: add_misc_stats.py
python scripts\02_processing\add_misc_stats.py
if errorlevel 1 (
    echo ERROR: Failed to add miscellaneous stats
    pause
    exit /b 1
)

echo.
echo Running: build_possession_based_features.py
python scripts\02_processing\build_possession_based_features.py
if errorlevel 1 (
    echo ERROR: Failed to build possession-based features
    pause
    exit /b 1
)

echo.
echo Running: validate_on_court_counts.py
python scripts\02_processing\validate_on_court_counts.py
if errorlevel 1 (
    echo ERROR: On-court validation failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo Your WNBA Prediction Engine is now ready!
echo.
echo Data files created:
echo - Raw boxscores, play-by-play, and team gamelogs in data\raw\
echo - Processed data with misc stats in data\processed\
echo - Possession-based player features in data\features\
echo.
echo To activate the environment in the future:
echo   cd wnba-prediction-engine
echo   venv\Scripts\activate.bat
echo.
echo To run individual scripts:
echo   python scripts\01_acquisition\script_name.py
echo   python scripts\02_processing\script_name.py
echo.
pause 