@echo off
REM Run AIVT environment bootstrap and start main app
cd /d %~dp0
echo Installing Python requirements (this may take a while)...
python -m pip install -r requirements.txt
echo Starting AIVT...
python main.py
pause
