@echo off
REM VAI — Start FastAPI backend + Nuxt 4 frontend
cd /d %~dp0

echo [VAI] Starting FastAPI backend on http://localhost:8000 ...
start "VAI Backend" cmd /k "python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload"

echo [VAI] Starting Nuxt frontend on http://localhost:3000 ...
start "VAI Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo VAI is starting...
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API docs: http://localhost:8000/docs
echo.
timeout /t 4 /nobreak >nul
start http://localhost:3000
