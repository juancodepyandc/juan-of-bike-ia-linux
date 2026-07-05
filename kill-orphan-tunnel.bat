@echo off
REM Recovery: tuer tous les cloudflared.exe puis relancer SEULEMENT celui de
REM start-aurora.bat. A utiliser une fois si v82c (update-aurora qui touchait
REM au tunnel) a laissé un cloudflared orphelin qui se bat avec celui de
REM start-aurora pour la connexion vers :3001.
title Aurora - kill orphan cloudflared
color 0C
cd /d "%~dp0"

echo.
echo ===================================================
echo  KILL TOUS LES cloudflared.exe ORPHELINS
echo ===================================================
echo.

tasklist /FI "IMAGENAME eq cloudflared.exe" /FO TABLE 2>&1
echo.
echo Killing...
taskkill /F /IM cloudflared.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   OK
) else (
    echo   Aucun cloudflared.exe en cours
)

echo.
echo ===================================================
echo  Maintenant relance start-aurora.bat
echo  pour avoir UN SEUL tunnel propre.
echo  start-aurora.bat affichera la nouvelle URL en clair
echo  dans sa cmd window principale.
echo ===================================================
echo.
pause
