@echo off
REM Autopilote professeur : ameliore en continu les modeles locaux d'Aurora (qwen2.5:7b, qwen2.5-coder:7b).
REM
REM Chaque semaine, avec le quota GPU Kaggle : entraineur et examinateur Kaggle (deux machines),
REM livraison et activation dans Ollama SEULEMENT si le candidat bat la version en place et regagne
REM l'examen tel que servi par Ollama. Sinon le modele en place reste. Reprise automatique apres arret.
REM
REM Prerequis : Ollama lance, identifiants Kaggle (%USERPROFILE%\.kaggle\kaggle.json),
REM             pip install kaggle datasets
REM Etat : Outputs\auto_rl\professor\autopilot\state.json
REM Arret : autopilot-aurora.bat stop      Etat : autopilot-aurora.bat status
REM Retour arriere d'un modele : python -m auto_rl.professor.install rollback --tag qwen2.5:7b
title Aurora - autopilote professeur
cd /d "%~dp0"
if /I "%~1"=="stop" (
    python -m auto_rl.professor.autopilot stop
    exit /b %ERRORLEVEL%
)
if /I "%~1"=="status" (
    python -m auto_rl.professor.autopilot status
    pause
    exit /b %ERRORLEVEL%
)
python -m auto_rl.professor.autopilot run %*
pause
