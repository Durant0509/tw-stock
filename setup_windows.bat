@echo off
chcp 65001 >nul
REM ============================================================
REM  台股策略作戰台 - Windows 一鍵設定
REM  用法: 把這個 .bat 放在 repo 資料夾裡, 雙擊執行
REM ============================================================
cd /d "%~dp0"
echo.
echo ============================================================
echo   台股策略作戰台 - 一鍵設定
echo ============================================================
echo.

REM --- 檢查 Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] 找不到 Python。請先安裝 Python 3:
    echo     https://www.python.org/downloads/
    echo     安裝時記得勾選 "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python 已安裝
python --version

REM --- 檢查 Git ---
git --version >nul 2>&1
if errorlevel 1 (
    echo [X] 找不到 Git。請先安裝: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo [OK] Git 已安裝
echo.

REM --- 首次全抓資料 ---
echo ============================================================
echo   步驟 1/2: 首次全抓三年資料 (約 1-2 小時, 只需一次)
echo   資料存在本機 data\ 資料夾, 不會上傳 GitHub
echo ============================================================
echo.
set /p GO="按 Enter 開始全抓 (或關掉視窗取消)... "
python bootstrap.py

echo.
echo ============================================================
echo   步驟 2/2: 建立每日自動更新排程 (一天兩次 15:30 / 21:30)
echo ============================================================
echo.

REM --- 建立兩個排程工作 ---
set REPO=%~dp0
set PYEXE=python
for /f "delims=" %%i in ('where python') do set PYEXE=%%i

schtasks /create /tn "tw-stock-update-1530" /tr "\"%PYEXE%\" \"%REPO%update.py\"" /sc daily /st 15:30 /f
schtasks /create /tn "tw-stock-update-2130" /tr "\"%PYEXE%\" \"%REPO%update.py\"" /sc daily /st 21:30 /f

echo.
echo ============================================================
echo   完成! 系統已設定好。
echo.
echo   - 每交易日 15:30 和 21:30 會自動更新
echo   - 電腦不關機就會自己跑
echo   - 打開網頁看最新狀況:
echo     https://durant0509.github.io/tw-stock/warroom.html
echo.
echo   (第一次自動更新要 push 回 GitHub, 屆時可能要求你登入 GitHub,
echo    照著輸入帳號和 token 即可, 只需一次)
echo ============================================================
pause
