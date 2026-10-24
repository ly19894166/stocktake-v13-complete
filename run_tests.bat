@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -X utf8 bootstrap.py --check
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -X utf8 -m pytest tests -q --junitxml=tests\test-results.xml
if errorlevel 1 goto failed
echo All tests passed.
pause
exit /b 0
:failed
echo Tests failed. See the errors above.
pause
exit /b 1
