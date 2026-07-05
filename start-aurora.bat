@echo off
title Aurora IA
color 0A
cd /d "%~dp0"

echo.
echo   ========================================
echo     AURORA IA - Demarrage complet
echo   ========================================
echo.

:: 1. Ollama — serialise model loads (anti-kernel-crash on 16 GB VRAM).
::    Sans ces vars, un 2e prompt brand pendant qu'un 1er est en cours
::    peut faire charger un 2e modele (ex: gemma3:27b 16.2 GB) en plus
::    du 1er, saturant VRAM + RAM systeme et crashant le driver display
::    Windows / le kernel. Memes valeurs que le spawner Tauri
::    (src-tauri/src/commands.rs:1792-1793).
echo   [1/5] Ollama (serialise: MAX_LOADED=1, NUM_PARALLEL=1)...
set OLLAMA_MAX_LOADED_MODELS=1
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_KEEP_ALIVE=10m
start "" /B "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve 2>nul
timeout /t 3 /nobreak >nul
echo          OK  http://127.0.0.1:11434

:: 2. ComfyUI
echo   [2/5] ComfyUI (FLUX + generation 3D)...
cd /d "%~dp0modele\comfyui\comfyui"
start "ComfyUI" /MIN cmd /c "venv\Scripts\python.exe main.py --listen 0.0.0.0 --port 8188"
cd /d "%~dp0application"
timeout /t 5 /nobreak >nul
echo          OK  http://127.0.0.1:8188

:: 3. Bridge
echo   [3/5] Bridge Python...
start "Bridge" /MIN cmd /c "python bridge_server.py"
timeout /t 4 /nobreak >nul
echo          OK  http://0.0.0.0:3001

:: 4. Vite
echo   [4/5] Vite dev...
start "Vite" /MIN cmd /c "npm run dev"
timeout /t 5 /nobreak >nul
echo          OK  http://localhost:1420

:: 5. Tunnel — pointe sur le BRIDGE (3001), pas sur Vite (1420).
::    Comme ca le tunnel reste up meme si Vite redemarre apres un edit qui
::    le casse. Le bridge proxy / -> Vite et affiche une page d'attente
::    quand Vite est down. L'URL trycloudflare ne change plus.
echo   [5/5] Tunnel Cloudflare (origin = bridge:3001)...
echo.

:: v82f — auto-copie de l'URL dans le presse-papier via wait-for-tunnel.ps1.
::   Le .ps1 surveille un log file ou cloudflared ecrit son output, capture
::   la 1ere ligne contenant https://*.trycloudflare.com, fait Set-Clipboard
::   et imprime l'URL sur stdout.
::   Ici on lance cloudflared en arriere-plan avec stdout/stderr redirige
::   vers un log temporaire, puis on appelle le .ps1 qui poll ce log.
set "CF_LOG=%TEMP%\aurora-cloudflared.log"
del /f /q "%CF_LOG%" 2>nul
start "Tunnel" /MIN cmd /c ""%~dp0tools\cloudflared.exe" tunnel --url http://localhost:3001 > "%CF_LOG%" 2>&1"

echo   ----------------------------------------
echo    Detection de l'URL en cours (max 45s)...
echo   ----------------------------------------
for /f "delims=" %%U in ('powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0tools\wait-for-tunnel.ps1" -LogFile "%CF_LOG%" -TimeoutSeconds 45') do set "TUNNEL_URL=%%U"

echo.
if defined TUNNEL_URL (
    echo   ========================================
    echo     URL TUNNEL : %TUNNEL_URL%
    echo   ========================================
    echo   ^(deja copiee dans ton presse-papier^)
    echo.
    REM Sauvegarde aussi dans tunnel_url.txt pour que SessionStart hook
    REM Claude la voit dans son banner d'ouverture.
    > "%~dp0tunnel_url.txt" echo %TUNNEL_URL%
) else (
    echo   [!] URL pas detectee en 45s. Ouvre le log :
    echo       %CF_LOG%
)

echo.
echo   La cmd window "Tunnel" minimise dans la taskbar continue de
echo   tourner — ferme-la pour stopper le tunnel.
echo.
pause
