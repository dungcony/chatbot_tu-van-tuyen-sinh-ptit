@echo off
REM run.bat - Chạy Chatbot TVTS trên máy Windows mới tinh (chưa có gì)
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo === Chatbot TVTS - Setup ^& Run ===

REM 1. Kiểm tra Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Loi: Can cai Python 3. Tai tai: https://www.python.org/downloads/
    echo Nho tick "Add Python to PATH" khi cai.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2^>nul') do set PYVER=%%v
echo Python: %PYVER%

REM 2. Tao virtual environment neu chua co
set VENV_DIR=%~dp0.venv
if not exist "%VENV_DIR%" (
    echo Tao virtual environment...
    python -m venv "%VENV_DIR%"
)

REM 3. Kich hoat venv va cai dependencies
echo Kich hoat venv va cai dependencies...
call "%VENV_DIR%\Scripts\activate.bat"

if not exist "%VENV_DIR%\.installed" (
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    type nul > "%VENV_DIR%\.installed"
    echo Da cai xong dependencies.
)

REM 4. Tao .env tu .envexample neu chua co
if not exist ".env" (
    if exist ".envexample" (
        copy .envexample .env >nul
        echo Da tao .env tu .envexample. Hay chinh sua .env (API key, MongoDB URI...) truoc khi chay.
    ) else (
        echo Loi: Khong tim thay .envexample de tao .env
        pause
        exit /b 1
    )
)

REM 5. Chay app
echo.
python sources\app.py

pause
