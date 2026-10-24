@echo off
setlocal
cd /d "%~dp0"
title Stocktake V13 Complete
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -X utf8 bootstrap.py
goto finished
:use_python
python -X utf8 bootstrap.py
:finished
if errorlevel 1 pause
endlocal
