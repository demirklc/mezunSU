@echo off
cd /d "%~dp0"
git fetch origin snapshots
if errorlevel 1 goto failed
git checkout FETCH_HEAD -- site/data
if errorlevel 1 goto failed
py scripts/build_site.py
if errorlevel 1 goto failed
echo Tarayicida http://127.0.0.1:8787 adresini acin.
py -m http.server 8787 --bind 127.0.0.1 --directory site
:failed
pause
