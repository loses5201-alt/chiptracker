@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo    ChipTracker 本機看盤
echo ============================================
echo.
echo [1/3] 嘗試更新最新資料 (git pull)...
git pull --quiet 2>nul
if errorlevel 1 (
  echo     ^(更新略過 - 用本機現有資料,不影響看盤^)
) else (
  echo     完成
)
echo.
echo [2/3] 開啟瀏覽器 http://localhost:8000/ ...
start "" http://localhost:8000/
echo.
echo [3/3] 啟動本機伺服器 (連接埠 8000)...
echo     ^>^>^> 關閉這個黑色視窗就會停止看盤 ^<^<^<
echo.
python -m http.server 8000
pause
