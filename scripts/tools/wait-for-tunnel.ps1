# Polls the cloudflared log file until the public tunnel URL appears, then
# prints just the URL on stdout (and copies it to the clipboard). The .bat
# captures stdout into a variable for display.
param(
    [Parameter(Mandatory=$true)] [string]$LogFile,
    [int]$TimeoutSeconds = 45
)

$pattern = 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'

for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path -LiteralPath $LogFile) {
        $match = Select-String -LiteralPath $LogFile -Pattern $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match) {
            $url = $match.Matches[0].Value
            try { $url | Set-Clipboard -ErrorAction SilentlyContinue } catch { }
            Write-Output $url
            return
        }
    }
}
# Timeout — emit nothing so the .bat can detect the absence.
