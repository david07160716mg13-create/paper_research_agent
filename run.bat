@echo off
echo ==========================================
echo   Paper Research Agent - Starting...
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/2] Installing dependencies...
pip install -r requirements.txt
echo.

echo [2/2] Starting server...
echo.
echo   Open http://localhost:8000 in your browser
echo   Press Ctrl+C to stop
echo.
start "" "http://localhost:8000"
python main.py
