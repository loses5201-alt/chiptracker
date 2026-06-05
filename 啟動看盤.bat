@echo off
cd /d "%~dp0"
echo ============================================
echo    ChipTracker - local viewer
echo ============================================
echo.
echo [1/3] Pulling latest data (git pull)...
git pull --quiet 2>nul
echo [2/3] Opening browser http://localhost:8000/ ...
start "" http://localhost:8000/
echo [3/3] Starting local server on port 8000...
echo      ^>^>^> Close this window to stop ^<^<^<
echo.
python -m http.server 8000
pause
