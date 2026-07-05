@echo off
REM Aurora bridge + Vite update — code-only, ne touche PAS au tunnel.
REM
REM start-aurora.bat gere le tunnel cloudflared (URL auto-copiee par
REM le user). update-aurora.bat ne fait que :
REM   1. pull origin/main + respawn bridge :3001 (bridge_doctor.py)
REM   2. cold restart Vite :1420 (HMR ne suit pas certains module-level changes)
REM   3. afficher status git
REM
REM Le tunnel reste pilote uniquement par start-aurora.bat. Pas de double
REM cloudflared, pas d'URL qui change a chaque update.
title Aurora - update code (tunnel intact)
color 0E
cd /d "%~dp0"

echo.
echo ===================================================
echo  AURORA - update code (le tunnel reste sur start-aurora)
echo ===================================================
echo.

REM 1. git fetch + reset --hard origin/main + bridge respawn
echo [1/3] bridge_doctor.py --pull
python bridge_doctor.py --pull
set DOCTOR_RC=%ERRORLEVEL%
echo bridge_doctor exit code : %DOCTOR_RC%
echo.

REM 2. cold restart Vite dev (HMR rate les changes utils/* main.tsx)
echo [2/3] restart Vite dev sur :1420
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":1420.*LISTENING"') do (
    echo   - kill PID %%P sur :1420
    taskkill /F /PID %%P 2>nul
)
timeout /t 1 /nobreak >nul
cd /d "%~dp0application"
start "Vite" /MIN cmd /c "npm run dev"
cd /d "%~dp0"
echo   Vite redemarre en arriere-plan ("Vite" dans la taskbar).
echo.

REM 3. status git
echo [3/3] status
git log -1 --format="HEAD: %%h %%s"
echo.

echo ===================================================
echo  Code mis a jour. Garde l'onglet du tunnel ouvert
echo  (URL inchangee de start-aurora) et fais Ctrl+F5
echo  pour forcer le re-bundle Vite cote navigateur.
echo  Si Vite met >10s : attends, le premier compile
echo  est plus long apres un cold restart.
echo ===================================================
echo.
pause
exit /b %DOCTOR_RC%
