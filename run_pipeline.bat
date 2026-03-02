@echo off
set PYTHONIOENCODING=utf-8
set LOGFILE=%~dp0logs\pipeline_%DATE:~-4,4%-%DATE:~-7,2%-%DATE:~-10,2%.log

if not exist "%~dp0logs" mkdir "%~dp0logs"

echo ============================================ >> "%LOGFILE%"
echo mindSHARE Pipeline - %DATE% %TIME% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"

cd /d "%~dp0"
"C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe" run_pipeline.py >> "%LOGFILE%" 2>&1

echo. >> "%LOGFILE%"
echo Done at %TIME% >> "%LOGFILE%"
