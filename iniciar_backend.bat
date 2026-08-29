@echo off
setlocal enableextensions
set "ING_DIR=%~dp0backend"
pushd "%ING_DIR%"

echo Iniciando INGESTA backend en puerto 5030...

set "PATH=%USERPROFILE%\.local\bin;%PATH%"

rem --- Liberar el puerto si esta ocupado (evita WinError 10048) ---
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5030" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1

if not exist "app\main.py" (
    echo ERROR: no se encontro app\main.py en %ING_DIR%
    popd
    endlocal
    exit /b 1
)

call :getbase "%ING_DIR%\.venv\pyvenv.cfg"
if defined BASEPY (
    set "PYTHONPATH=%ING_DIR%\.venv\Lib\site-packages"
    "%BASEPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 5030
    goto :fin
)

set "VIRTUAL_ENV="
uv run uvicorn app.main:app --host 127.0.0.1 --port 5030

:fin
popd
endlocal
goto :eof

rem =====================================================================
rem  Subrutina: obtiene el interprete base de un pyvenv.cfg.
rem  %1 = ruta al pyvenv.cfg ; devuelve la ruta a python.exe en %BASEPY%
rem =====================================================================
:getbase
set "BASEPY="
set "_home="
if not exist "%~1" goto :eof
for /f "usebackq tokens=1,* delims== " %%a in ("%~1") do if /i "%%a"=="home" set "_home=%%b"
if defined _home if exist "%_home%\python.exe" set "BASEPY=%_home%\python.exe"
goto :eof
