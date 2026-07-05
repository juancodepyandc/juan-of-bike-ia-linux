@echo off
REM One-liner pour finir le push GitHub privé.
REM Requis une seule fois : l'authentification gh via navigateur.

setlocal enabledelayedexpansion

set GH=gh
where gh >nul 2>&1 || set GH="C:\Program Files\GitHub CLI\gh.exe"

%GH% auth status >nul 2>&1
if errorlevel 1 (
  echo [+] Authentification GitHub requise. Le navigateur va s'ouvrir...
  %GH% auth login --hostname github.com --git-protocol https --web --skip-ssh-key
  if errorlevel 1 (
    echo [x] Authentification echouee.
    pause
    exit /b 1
  )
)

if not exist .git (
  echo [x] Ce script doit etre lance depuis la racine du projet AuroraIA-v2.
  pause
  exit /b 1
)

REM Pousse la branche main
git branch -M main

REM Tente de creer le repo prive + pousser
echo [+] Creation du repo prive juan-of-bike-ia...
%GH% repo create juan-of-bike-ia --private --source . --remote origin --push

if errorlevel 1 (
  echo [!] Le repo existe peut-etre deja, tentative de push direct...
  git remote remove origin 2>nul
  for /f "delims=" %%u in ('%GH% api user --jq .login') do set GH_USER=%%u
  git remote add origin https://github.com/!GH_USER!/juan-of-bike-ia.git
  git push -u origin main
)

echo.
echo [OK] Push termine. Ton repo est visible sur github.com/^<ton-compte^>/juan-of-bike-ia (prive).
endlocal
pause
