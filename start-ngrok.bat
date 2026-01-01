@echo off
echo ========================================
echo  Artisting Legal GraphRAG - ngrok Setup
echo ========================================
echo.

echo Starting ngrok tunnels...
echo.
echo This will create two public URLs:
echo 1. Backend API (port 8000)
echo 2. Frontend (port 3001)
echo.
echo Press Ctrl+C to stop all tunnels
echo.

REM Start ngrok for backend on port 8000
start "ngrok-backend" ngrok http 8000 --log=stdout

REM Wait a moment for first tunnel to initialize
timeout /t 3 /nobreak >nul

REM Start ngrok for frontend on port 3001
start "ngrok-frontend" ngrok http 3001 --log=stdout

echo.
echo ========================================
echo Tunnels started!
echo ========================================
echo.
echo IMPORTANT NEXT STEPS:
echo.
echo 1. Open http://localhost:4040 to see the ngrok dashboard
echo    - Copy the Backend URL (port 8000)
echo    - Copy the Frontend URL (port 3001)
echo.
echo 2. Update frontend environment:
echo    - Edit frontend-legal\.env.local
echo    - Set NEXT_PUBLIC_API_URL to your backend ngrok URL
echo.
echo 3. Restart your frontend development server
echo.
echo 4. Share the FRONTEND ngrok URL with your client
echo.
echo ========================================
echo.
pause
