@echo off
rem Relance ComfyUI + cloudflared (extrait de start-aurora.bat, sans pause)
cd /d "C:\Users\Juan\Desktop\ia\AuroraIA-v2\modele\comfyui\comfyui"
start "ComfyUI" /MIN cmd /c "venv\Scripts\python.exe main.py --listen 0.0.0.0 --port 8188"
set "CF_LOG=%TEMP%\aurora-cloudflared.log"
del /f /q "%CF_LOG%" 2>nul
start "Tunnel" /MIN cmd /c ""C:\Users\Juan\Desktop\ia\AuroraIA-v2\tools\cloudflared.exe" tunnel --url http://localhost:3001 > "%CF_LOG%" 2>&1"
echo lances
