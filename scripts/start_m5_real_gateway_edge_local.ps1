$ErrorActionPreference = 'Stop'
$root = 'D:\code\opencode\genb'
$gatewayDir = Join-Path $root 'genb-data-plane-gateway'
$python = 'C:\Users\szhar\AppData\Local\Python\bin\python.exe'
$logDir = Join-Path $root '.logs\m5-real-gate'
$agentId = 'core-component-demo-agent'

function Read-ProtectedSecret([string]$Path) {
    $secure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}
function Wait-Ready([string]$Url, [Diagnostics.Process]$Process) {
    $deadline = (Get-Date).AddSeconds(45)
    do {
        if ($Process.HasExited) { throw "Process $($Process.Id) exited with code $($Process.ExitCode)" }
        try { $health = Invoke-RestMethod -Uri $Url -TimeoutSec 2 } catch { $health = $null }
        if ($health.status -eq 'UP') { return }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url"
}
foreach ($port in 18080) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use"
    }
}
$credential = Read-ProtectedSecret (Join-Path $root ".local-secrets\$agentId.credential.dpapi")
$internal = Read-ProtectedSecret (Join-Path $root '.local-secrets\genb-component-internal-token.dpapi')
$env:PYTHONPATH = $gatewayDir
$env:GENB_CONTROL_URL = 'http://127.0.0.1:8581'; $env:GENB_GATEWAY_MACHINE_TOKEN = $internal
$env:GENB_GATEWAY_HOST = '127.0.0.1'; $env:GENB_GATEWAY_PORT = '18080'
$env:GENB_PUBLIC_ORIGIN = 'http://127.0.0.1:18081'; $env:GENB_PORTAL_AUTHORIZE_URL = 'http://127.0.0.1:18716/'
$env:GENB_GATEWAY_CALLBACK_URL = 'http://127.0.0.1:18081/agents/_auth/callback'
$env:GENB_NGINX_TOKEN = 'nginx-only'; $env:GENB_INVALIDATION_TOKEN = 'm5-local-invalidation-only'
$env:GENB_REDIS_HOST = '127.0.0.1'; $env:GENB_REDIS_PORT = '16380'; $env:GENB_REDIS_PASSWORD = ''
$env:GENB_ALLOWED_UPSTREAMS = '127.0.0.1:18714,127.0.0.1:18702,127.0.0.1:18704,127.0.0.1:18705,127.0.0.1:18712'
$env:GENB_AGENT_CREDENTIALS = "$agentId=$credential"
$env:GENB_SECRET_CORE_COMPONENTS_RUNTIME = $credential
$gateway = Start-Process -FilePath $python -ArgumentList @('-m', 'genb_gateway.server') `
    -WorkingDirectory $gatewayDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'gateway.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'gateway.stderr.log') -PassThru
Wait-Ready 'http://127.0.0.1:18080/health/ready' $gateway

if (-not $env:GENB_LOCAL_JWT_SECRET) {
    throw '请先通过本地安全配置设置 GENB_LOCAL_JWT_SECRET，脚本不提供固定Secret。'
}
$env:GENB_BASE_URL = 'http://127.0.0.1:8581/api'
$portalListener = Get-NetTCPConnection -LocalPort 18716 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $portalListener) {
    $portal = Start-Process -FilePath $python -ArgumentList @('tests\m5_real_portal.py') `
        -WorkingDirectory $gatewayDir -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir 'portal.stdout.log') `
        -RedirectStandardError (Join-Path $logDir 'portal.stderr.log') -PassThru
} else {
    $portal = Get-Process -Id $portalListener.OwningProcess
}
$deadline = (Get-Date).AddSeconds(15)
do { $ready = Test-NetConnection 127.0.0.1 -Port 18716 -InformationLevel Quiet; if (-not $ready) { Start-Sleep -Milliseconds 200 } } `
    while (-not $ready -and (Get-Date) -lt $deadline)
if (-not $ready) { throw 'Portal fixture did not become ready' }

if (-not (Get-NetTCPConnection -LocalPort 18081 -State Listen -ErrorAction SilentlyContinue)) {
    & 'D:\JAVA\tool\nginx-1.31.3\nginx.exe' -p 'D:\JAVA\tool\nginx-1.31.3' `
        -c 'D:/code/opencode/genb/genb-data-plane-gateway/nginx/genb-gateway.local.conf'
}
$deadline = (Get-Date).AddSeconds(15)
do { $ready = Test-NetConnection 127.0.0.1 -Port 18081 -InformationLevel Quiet; if (-not $ready) { Start-Sleep -Milliseconds 200 } } `
    while (-not $ready -and (Get-Date) -lt $deadline)
if (-not $ready) { throw 'Nginx did not become ready' }
[pscustomobject]@{ Gateway = $gateway.Id; Portal = $portal.Id; ConfigVersion = 3 }
