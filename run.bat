@echo off
echo Starting Binance Credit Card Purchase Tracker v0.1...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if requirements are installed
python -c "import httpx, pydantic, dotenv, tenacity, pyqtgraph" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install requirements
        pause
        exit /b 1
    )
)

REM Run the application
echo Launching application...
python main.py

echo.
echo Application closed.
pause
