@echo off
REM update-aurora-prod.bat — pull + build + restart vite preview (prod).
REM
REM Use this instead of update-aurora.bat when the tunnel is in prod mode
REM (vite preview serving application/dist/ on port 1420). Workflow :
REM   1. pull origin/main + respawn bridge :3001 (bridge_doctor.py)
REM   2. vite build (prod bundle, ~1-2 s)
REM   3. cold restart vite preview on :1420 so the new dist/ serves
REM   4. show git status
REM
REM Tunnel cloudflared is unaffected (still pointed at :1420), so the
REM URL stays the same. Just Ctrl+F5 in the browser to pick up the new
REM bundle hashes.
title Aurora - update PROD (tunnel intact)
color 0A
cd /d "%~dp0"

echo.
echo ===================================================
echo  AURORA - update PROD (le tunnel reste sur start-aurora)
echo ===================================================
echo.

REM 0. cleanup cruft (fichiers stderr/stdout/notes ad-hoc)
echo [0/7] clean-cruft (artefacts dev a supprimer)
if exist "clean-cruft.bat" (
    call clean-cruft.bat
) else (
    echo  - clean-cruft.bat absent, skip
)
echo.

REM 0b. bump extension version si changement detecte (auto-reload Aurora-Connect)
echo [0b/7] bump-extension-version (auto-reload extension si change)
if exist "bump-extension-version.py" (
    python bump-extension-version.py
) else (
    echo  - bump-extension-version.py absent, skip
)
echo.

REM 1. git fetch + reset --hard origin/main + bridge respawn
echo [1/7] bridge_doctor.py --pull
python bridge_doctor.py --pull
set DOCTOR_RC=%ERRORLEVEL%
echo bridge_doctor exit code : %DOCTOR_RC%
echo.

REM 2. vite build (regenerates application/dist/)
echo [2/7] npm run build
cd /d "%~dp0application"
call npm run build
set BUILD_RC=%ERRORLEVEL%
cd /d "%~dp0"
if not "%BUILD_RC%"=="0" (
    echo.
    echo  *** BUILD FAILED *** keeping current preview running, no swap.
    pause
    exit /b %BUILD_RC%
)
echo.

REM 3. cold restart vite preview on :1420
echo [3/7] restart vite preview sur :1420
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":1420.*LISTENING"') do (
    echo   - kill PID %%P sur :1420
    taskkill /F /PID %%P 2>nul
)
timeout /t 1 /nobreak >nul
cd /d "%~dp0application"
start "Vite preview" /MIN cmd /c "npm run preview:tunnel"
cd /d "%~dp0"
echo   vite preview redemarre en arriere-plan ("Vite preview" dans la taskbar).
echo.

REM 4. status git
echo [4/7] status
git log -1 --format="HEAD: %%h %%s"
echo.

REM 5. anti-crash module smoke (post-build verification)
echo [5/7] aurora_module_smoke.py
REM Wait a few seconds for vite preview to finish booting before probing
timeout /t 3 /nobreak >nul
python .claude\hooks\aurora_module_smoke.py
set SMOKE_RC=%ERRORLEVEL%
if not "%SMOKE_RC%"=="0" (
    echo.
    echo  *** SMOKE BLOCK *** un module est casse — voir checks ci-dessus.
    echo  Le bundle est deja deploye, mais quelque chose plante. Investigue
    echo  AVANT le prochain Ctrl+F5 du user.
)
echo.

echo ===================================================
echo  Bundle prod regenere. Tunnel inchange.
echo  Ctrl+F5 dans le navigateur pour charger le nouveau
echo  bundle (les hashes dans /assets/ ont change).
echo ===================================================
echo.
pause
exit /b %DOCTOR_RC%
