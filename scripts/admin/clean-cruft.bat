@echo off
REM clean-cruft.bat — supprime les fichiers d'artefacts dev/test à la racine.
REM
REM Cible :
REM   - application\*.stderr  (sortie redirigée stderr de tests Python/Node)
REM   - application\*.stdout  (idem stdout)
REM   - application\bridge_test.log
REM   - .\10s  (typo de commande devenu fichier)
REM   - .\3D.txt  (note ad-hoc)
REM
REM Garde intacts :
REM   - _design_unzip/  (sources design référencées en CHANGELOG)
REM   - application/bridge_state/  (runtime state brand_enrich_cache)
REM   - application/extension/  (Chrome extension réelle)
REM   - application/mobile/, application/bin/  (potentiel build artifacts)
REM   - application/python-services/MuseTalk/  (modèle checkpoint)
REM
REM Usage : double-clic ou `clean-cruft.bat` depuis racine projet.
title Aurora - clean cruft
color 0E
cd /d "%~dp0"

echo.
echo ===================================================
echo  AURORA - clean cruft (fichiers dev/test inutiles)
echo ===================================================
echo.

set TOTAL=0
set DELETED=0

REM 1. Fichiers stderr/stdout dans application/
echo [1/4] application\*.stderr
for %%f in (application\*.stderr) do (
    set /a TOTAL+=1
    if exist "%%f" (
        del /f /q "%%f"
        if not exist "%%f" set /a DELETED+=1
        echo   - delete %%f
    )
)
echo.

echo [2/4] application\*.stdout
for %%f in (application\*.stdout) do (
    set /a TOTAL+=1
    if exist "%%f" (
        del /f /q "%%f"
        if not exist "%%f" set /a DELETED+=1
        echo   - delete %%f
    )
)
echo.

REM 3. Logs ad-hoc
echo [3/4] logs ad-hoc
for %%f in (application\bridge_test.log) do (
    if exist "%%f" (
        set /a TOTAL+=1
        del /f /q "%%f"
        if not exist "%%f" set /a DELETED+=1
        echo   - delete %%f
    )
)
echo.

REM 4. Fichiers/notes racine
echo [4/4] notes racine
if exist "10s" (
    set /a TOTAL+=1
    del /f /q "10s"
    if not exist "10s" set /a DELETED+=1
    echo   - delete 10s
)
if exist "3D.txt" (
    set /a TOTAL+=1
    del /f /q "3D.txt"
    if not exist "3D.txt" set /a DELETED+=1
    echo   - delete 3D.txt
)
echo.

echo ===================================================
echo  Cleanup termine : %DELETED% / %TOTAL% fichiers supprimes.
echo ===================================================
echo.
echo  Note : les directories _design_unzip\, application\bridge_state\,
echo  application\extension\ sont conservees (sources legitimes).
echo.
exit /b 0
