# =====================================================================
# Aurora -- relance Chrome en mode debug pour superviser Claude Design
# Usage : & "C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\scripts\start-chrome-debug.ps1"
# =====================================================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " AURORA -- Chrome debug bridge" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1/4 : tuer toutes les instances de Chrome ------------------------
Write-Host "[1/4] Fermeture de toutes les instances Chrome..." -ForegroundColor Yellow
$killed = Get-Process chrome -ErrorAction SilentlyContinue
if ($killed) {
    $killed | Stop-Process -Force
    Write-Host "      $($killed.Count) processus Chrome ferme(s)." -ForegroundColor Green
} else {
    Write-Host "      Aucun Chrome ouvert." -ForegroundColor Green
}
Start-Sleep -Seconds 2

# --- 2/4 : detecter le chemin de chrome.exe ---------------------------
Write-Host ""
Write-Host "[2/4] Detection du chemin Chrome..." -ForegroundColor Yellow
$chrome = $null
$candidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
foreach ($p in $candidates) {
    if (Test-Path $p) { $chrome = $p; break }
}
if (-not $chrome) {
    Write-Host "      ERREUR : chrome.exe introuvable." -ForegroundColor Red
    Write-Host "      Cherche-le sur ton disque puis edite ce script." -ForegroundColor Red
    exit 1
}
Write-Host "      $chrome" -ForegroundColor Green

# --- 3/4 : lancer Chrome avec --remote-debugging-port=9222 ------------
Write-Host ""
Write-Host "[3/4] Lancement de Chrome sur port 9222..." -ForegroundColor Yellow
$userData = "$env:LOCALAPPDATA\Google\Chrome\User Data"
$chromeArgs = @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$userData"
)
Start-Process -FilePath $chrome -ArgumentList $chromeArgs
Write-Host "      Lance. Attente 5s..." -ForegroundColor Green
Start-Sleep -Seconds 5

# --- 4/4 : verifier que le port repond --------------------------------
Write-Host ""
Write-Host "[4/4] Verification du port debug..." -ForegroundColor Yellow
$ok = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:9222/json/version" -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -eq 200) { $ok = $true }
} catch {
    $ok = $false
}

Write-Host ""
if ($ok) {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host " OK -- Chrome ecoute sur localhost:9222" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "ETAPES SUIVANTES (a faire toi-meme) :" -ForegroundColor Cyan
    Write-Host ""
    Write-Host " A) Dans la fenetre Chrome qui vient de s'ouvrir," -ForegroundColor White
    Write-Host "    va sur ton design Claude :" -ForegroundColor White
    Write-Host ""
    Write-Host "    https://claude.ai/design/p/019de062-6926-72a0-9e0d-024fe8e8cad7?file=Aurora_v4.html" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Si Cloudflare te montre la case 'Verifiez que vous etes humain'," -ForegroundColor White
    Write-Host "    clique-la TOI-MEME (ca passe, c'est une vraie session)." -ForegroundColor White
    Write-Host ""
    Write-Host " B) Reviens dans ce terminal et tape ces 2 commandes :" -ForegroundColor White
    Write-Host ""
    Write-Host "    claude mcp add chrome-cdp -- npx -y chrome-devtools-mcp@latest --browserUrl http://localhost:9222" -ForegroundColor Yellow
    Write-Host "    claude" -ForegroundColor Yellow
    Write-Host ""
    Write-Host " C) Dans Claude Code qui s'ouvre :" -ForegroundColor White
    Write-Host "    Tape  /resume  et choisis la conversation 'Aurora v82nu iter22'." -ForegroundColor White
    Write-Host ""
    Write-Host " D) Une fois revenu, ecris-lui : 'branche, vas-y'." -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host " ERREUR -- port 9222 ne repond pas" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Cause probable : un Chrome tournait deja en arriere-plan" -ForegroundColor Yellow
    Write-Host "et a absorbe la commande sans activer le port debug." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Solution :" -ForegroundColor Cyan
    Write-Host "  1. Ouvre le Gestionnaire de taches (Ctrl+Shift+Echap)"
    Write-Host "  2. Onglet 'Details', tri par nom, ferme TOUT chrome.exe"
    Write-Host "  3. Relance ce script."
    Write-Host ""
    exit 1
}
