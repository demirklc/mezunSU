@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Tarayicida http://127.0.0.1:8787 adresini acin.
py -m uvicorn main:app --host 127.0.0.1 --port 8787
:failed
pause
