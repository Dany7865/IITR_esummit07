
@echo off
cd /d "%~dp0"
echo Starting HPCL Lead Intelligence...
python app.py
if errorlevel 1 (
  echo.
  echo If you see "No module named 'X'", run: pip install -r requirements.txt
  pause
)
