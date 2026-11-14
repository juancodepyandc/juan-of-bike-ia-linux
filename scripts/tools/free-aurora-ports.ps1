# Kill any process holding the ports Aurora IA uses, so a fresh start
# never collides with a stale instance from a previous run.
# Called by start-aurora.bat before launching services.
#
# Pass -IncludeOllama to ALSO kill any running Ollama process. Use this when
# Ollama is stuck (e.g. /api/ps shows no model after several minutes for a
# request that should have loaded a model in seconds).
param(
    [int[]]$Ports = @(1420, 3001, 8188, 11434),
    [switch]$IncludeOllama
)

$ErrorActionPreference = 'SilentlyContinue'

foreach ($port in $Ports) {
    # Get-NetTCPConnection works on Win10+ and is more reliable than netstat parsing.
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { continue }

    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        if ($pid -le 4) { continue }  # 0/4 = system idle / system, never kill
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if (-not $proc) { continue }
            $name = $proc.ProcessName
            # By default skip Ollama on 11434 -- it's a system service Aurora reuses.
            # Use -IncludeOllama to force-kill it (when Ollama is stuck).
            if ($port -eq 11434 -and $name -like 'ollama*' -and -not $IncludeOllama) {
                Write-Host "  port $port : Ollama deja actif (reuse -- utilise -IncludeOllama pour le tuer)"
                continue
            }
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  port $port : process $name (PID $pid) tue"
        } catch {
            # Ignore -- kill best-effort
        }
    }
}

# Belt-and-suspenders: if -IncludeOllama, also hunt down ollama.exe processes
# that aren't bound to a port yet (e.g. mid-spawn, holding GPU memory).
if ($IncludeOllama) {
    Get-Process -Name 'ollama*' -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            Write-Host "  ollama : process $($_.ProcessName) (PID $($_.Id)) tue"
        } catch { }
    }
}

# Also clean up the ComfyUI DB lock file if it exists (stale lock from crash).
$comfyDb = "$PSScriptRoot\..\modele\comfyui\comfyui\user\comfyui.db"
$comfyLock = "$comfyDb-journal"
if (Test-Path $comfyLock) {
    Remove-Item $comfyLock -Force -ErrorAction SilentlyContinue
    Write-Host "  ComfyUI DB lock supprime (stale journal)"
}

# Brief pause so the OS releases the ports before new services bind.
Start-Sleep -Milliseconds 800
