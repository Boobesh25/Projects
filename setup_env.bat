@echo off
echo ============================================
echo   GenAI Project Chat - Environment Setup
echo ============================================
echo.

echo [1/4] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment. Ensure Python 3.11+ is installed.
    pause
    exit /b 1
)

echo [2/4] Activating environment...
call venv\Scripts\activate.bat

echo [3/4] Upgrading pip...
python -m pip install --upgrade pip

echo [4/4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Prerequisites:
echo   - PostgreSQL running with database 'genai_chat' created
echo   - Google Gemini API key
echo.
echo Next steps:
echo   1. Copy .env.example to .env and fill in your GEMINI_API_KEY
echo   2. Create PostgreSQL database:
echo      psql -U postgres -c "CREATE DATABASE genai_chat;"
echo   3. Start backend:  python run_api.py
echo   4. Start frontend: python run_frontend.py
echo.
pause
