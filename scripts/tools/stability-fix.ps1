# =====================================================================
# Aurora — stability-fix.ps1
# Mitigations LOGICIELLES pour les BSOD pendant la generation 3D.
#
# !!! Ceci ne GUERIT pas la cause racine !!!
# La cause = instabilite memoire DDR5-6000 EXPO sur Ryzen 9950X /
# X870E Hero en BIOS 1103. Le vrai correctif est dans le BIOS
# (mise a jour 1805+ AGESA, Memory Context Restore OFF, VSOC ~1.25V,
# FCLK 2000, ou descendre la RAM a 5200). Voir le plan donne par Aurora.
#
# Ce script REDUIT le declencheur (pics de courant GPU) et CAPTURE la
# preuve du prochain crash (dump) pour analyse.
#
# LANCER EN ADMIN :
#   clic droit PowerShell > "Executer en tant qu'administrateur"
#   puis :  powershell -ExecutionPolicy Bypass -File tools\stability-fix.ps1
# =====================================================================

param(
    [int]$PowerLimitWatts = 280,   # cap GPU (max carte = 350W, defaut usine = 320W)
    [switch]$NoAutoReboot           # si present : laisse le code BSOD a l'ecran au lieu de redemarrer
)

$ErrorActionPreference = 'Continue'

function Test-Admin {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    return ([System.Security.Principal.WindowsPrincipal]$id).IsInRole(
        [System.Security.Principal.WindowsBuiltinRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "[X] Pas en administrateur. Relance PowerShell en admin puis :" -ForegroundColor Red
    Write-Host "    powershell -ExecutionPolicy Bypass -File tools\stability-fix.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "==== Aurora stability-fix (admin OK) ====" -ForegroundColor Cyan

# --- 1) Cap de puissance GPU : reduit les pics transitoires qui font ----
# --- chuter l'alim et corrompent la RAM marginale pendant la 3D.    ----
$smi = "$env:ProgramFiles\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
if (-not (Test-Path $smi)) { $smi = "nvidia-smi" }   # souvent dans le PATH
Write-Host "`n[1] Cap puissance GPU a $PowerLimitWatts W..." -ForegroundColor Cyan
& $smi -pl $PowerLimitWatts
& $smi --query-gpu=name,enforced.power.limit,power.max_limit --format=csv,noheader

# Re-appliquer le cap a chaque demarrage (le cap GeForce ne persiste pas) :
$taskName = "AuroraGpuPowerCap"
$action   = New-ScheduledTaskAction -Execute $smi -Argument "-pl $PowerLimitWatts"
$trigger  = New-ScheduledTaskTrigger -AtStartup
$principal= New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Principal $principal -Force -ErrorAction Stop | Out-Null
    Write-Host "    -> tache planifiee '$taskName' creee (re-applique le cap au boot)." -ForegroundColor Green
} catch {
    Write-Host "    -> tache planifiee non creee: $($_.Exception.Message)" -ForegroundColor Yellow
}

# --- 2) Capture du prochain crash : dump minidump garanti -------------
Write-Host "`n[2] Configuration capture de crash (dump)..." -ForegroundColor Cyan
$cc = 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl'
Set-ItemProperty $cc -Name CrashDumpEnabled    -Value 7 -Type DWord   # automatic (kernel+minidump)
Set-ItemProperty $cc -Name AlwaysKeepMemoryDump -Value 1 -Type DWord
Set-ItemProperty $cc -Name MinidumpDir         -Value "$env:SystemRoot\Minidump" -Type ExpandString
if ($NoAutoReboot) {
    Set-ItemProperty $cc -Name AutoReboot -Value 0 -Type DWord
    Write-Host "    -> AutoReboot OFF : le code STOP restera affiche a l'ecran." -ForegroundColor Green
} else {
    Write-Host "    -> AutoReboot inchange (relance `+ NoAutoReboot pour voir le code STOP)." -ForegroundColor Green
}
# pagefile gere par le systeme (necessaire pour ecrire un dump)
$cs = Get-CimInstance Win32_ComputerSystem
if (-not $cs.AutomaticManagedPagefile) {
    Write-Host "    -> pagefile en mode manuel ; on laisse tel quel (commit OK)." -ForegroundColor Yellow
}
Write-Host "    -> dumps -> $env:SystemRoot\Minidump (donne-les a Aurora apres un crash)." -ForegroundColor Green

Write-Host "`n==== Termine. Rappel : le VRAI fix est dans le BIOS. ====" -ForegroundColor Cyan
