@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   Chatbot Tu van Tuyen sinh PTIT - Setup and Run
echo ============================================================
echo.

REM ============================================================
REM  BUOC 1: Tim Python
REM ============================================================
set PYTHON_EXE=

REM Thu cac duong dan cu the truoc (tranh Windows Store alias)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
if exist "C:\Python313\python.exe" set PYTHON_EXE=C:\Python313\python.exe
if exist "C:\Python312\python.exe" set PYTHON_EXE=C:\Python312\python.exe
if not "%PYTHON_EXE%"=="" goto :check_version

REM Thu py launcher
py -3 --version >nul 2>nul
if %errorlevel% equ 0 set PYTHON_EXE=py -3
if not "%PYTHON_EXE%"=="" goto :check_version

REM Thu python trong PATH (co the la Store alias - se kiem tra sau)
python --version >nul 2>nul
if %errorlevel% equ 0 set PYTHON_EXE=python
if not "%PYTHON_EXE%"=="" goto :check_version

REM ============================================================
REM  BUOC 2: Khong co Python -> Tu dong tai va cai
REM ============================================================
echo [WARN] Khong tim thay Python. Dang tu dong tai Python 3.13.2...
echo.

set PY_URL=https://www.python.org/ftp/python/3.13.2/python-3.13.2-amd64.exe
set PY_INSTALLER=%TEMP%\python-installer.exe

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing"

if not exist "%PY_INSTALLER%" (
    echo [FAIL] Tai Python that bai. Kiem tra ket noi mang.
    echo        Hoac tai thu cong: https://www.python.org/downloads/
    echo        Nho tick "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [....] Dang cai Python, vui long doi 1-2 phut...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_launcher=1
set INST_ERR=%errorlevel%
del "%PY_INSTALLER%" >nul 2>nul

if %INST_ERR% neq 0 (
    echo [FAIL] Cai Python that bai. Thu cai thu cong:
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Da cai Python thanh cong.
set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

:check_version
"%PYTHON_EXE%" --version
if %errorlevel% neq 0 (
    echo [FAIL] Khong chay duoc Python. Thu dong va mo lai CMD.
    pause
    exit /b 1
)
echo.

REM ============================================================
REM  BUOC 3: Tao virtual environment
REM ============================================================
set VENV=%~dp0.venv

if not exist "%VENV%\Scripts\activate.bat" (
    echo [....] Dang tao virtual environment...
    "%PYTHON_EXE%" -m venv "%VENV%"
    if %errorlevel% neq 0 (
        echo [FAIL] Tao venv that bai. Thu xoa thu muc .venv va chay lai.
        pause
        exit /b 1
    )
    echo [OK] Da tao venv.
    echo.
)

REM ============================================================
REM  BUOC 4: Kich hoat venv
REM ============================================================
call "%VENV%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [FAIL] Kich hoat venv that bai.
    pause
    exit /b 1
)

REM ============================================================
REM  BUOC 5: Cai dependencies
REM ============================================================
if exist "%VENV%\.deps_installed" goto :deps_done

echo [....] Dang cai dependencies, vui long cho...
echo.

python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Cai dependencies that bai.
    echo        Thu xoa thu muc .venv roi chay lai.
    echo.
    pause
    exit /b 1
)

type nul > "%VENV%\.deps_installed"
echo.
echo [OK] Da cai xong dependencies.
echo.
goto :deps_check_env

:deps_done
echo [OK] Dependencies da san sang.

:deps_check_env

REM ============================================================
REM  BUOC 6: Kiem tra .env
REM ============================================================
if exist ".env" goto :run_app

if exist ".envexample" (
    copy .envexample .env >nul
    echo [WARN] Da tao .env tu .envexample.
    echo        Hay chinh sua file .env truoc khi chay.
    echo.
    notepad .env
    pause
    goto :run_app
)

echo [FAIL] Khong tim thay file .env
echo        Tao file .env voi noi dung:
echo.
echo        GEMINI_API_KEY=your_api_key_here
echo        MONGO_URI=your_mongodb_uri_here
echo        DB_NAME=tuvantuyensinh
echo.
pause
exit /b 1

:run_app
REM ============================================================
REM  BUOC 7: Chay ung dung
REM ============================================================
echo.
echo ============================================================
echo   Dang khoi dong server...
echo   Nhan Ctrl+C de dung.
echo ============================================================
echo.

python sources\app.py

echo.
if %errorlevel% neq 0 (
    echo [FAIL] App thoat voi loi %errorlevel%.
) else (
    echo [OK] Server da dung.
)
echo.
pause
