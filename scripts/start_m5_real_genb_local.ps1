$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$logDir = Join-Path $root '.logs\m5-real-gate'
$backendDir = Join-Path $root 'gen-b\gen-b-backend'

function Read-ProtectedSecret([string]$Path) {
    $secure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

if (Get-NetTCPConnection -LocalPort 8581 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8581 is already in use'
}
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$redisLine = Select-String -LiteralPath 'D:\environment\redis\redis.windows-service.conf' `
    -Pattern '^\s*requirepass\s+(\S+)' | Select-Object -First 1
if (-not $redisLine) { throw 'Local Redis password is not configured' }

$env:JAVA_HOME = 'D:\JAVA\JDK\temurin-21'
$env:GENB_REDIS_HOST = '127.0.0.1'
$env:GENB_REDIS_PORT = '6379'
$env:GENB_REDIS_PASSWORD = $redisLine.Matches[0].Groups[1].Value
$env:CONTROL_SYSTEM_INTERNAL_TOKEN = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\genb-component-internal-token.dpapi'
)
$env:COMPONENT_ACTOR_KEY_ID = 'genb-local-m5-real'
$env:COMPONENT_ACTOR_PRIVATE_KEY_PATH = Join-Path $backendDir 'local-iteration11-actor.pem'
$env:GENB_TENANT_ID = 'genb-local'
$build = Join-Path $root '.tmp\genb-backend-m5-real'
$process = Start-Process -FilePath 'D:\environment\maven\apache-maven-3.6.3\bin\mvn.cmd' `
    -ArgumentList @("-Dgenb.build.directory=$build", 'spring-boot:run') `
    -WorkingDirectory $backendDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'genb.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'genb.stderr.log') -PassThru

$deadline = (Get-Date).AddSeconds(100)
do {
    if ($process.HasExited) { throw "GenB exited with code $($process.ExitCode)" }
    try { $health = Invoke-RestMethod 'http://127.0.0.1:8581/api/actuator/health' -TimeoutSec 2 }
    catch { $health = $null }
    if ($health.status -eq 'UP') { break }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)
if ($health.status -ne 'UP') { throw 'GenB did not become ready' }

[pscustomobject]@{ Pid = $process.Id; Status = $health.status; Url = 'http://127.0.0.1:8581/api' }
