$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$port = 18701
$listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    $running = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($running.CommandLine -notlike '*control_system.main:create_application*--port 18701*') {
        throw '18701不是预期Control System进程，拒绝重启'
    }
    Stop-Process -Id $listener.OwningProcess -Force
}

function Read-ProtectedSecret([string]$Path) {
    $secure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

$internalToken = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\genb-component-internal-token.dpapi'
)
$credential = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\core-component-demo-agent.credential.dpapi'
)
$redisMatch = Select-String -LiteralPath 'D:\environment\redis\redis.windows-service.conf' `
    -Pattern '^\s*requirepass\s+(\S+)' | Select-Object -First 1
if (-not $redisMatch) { throw 'Redis密码配置缺失' }

$env:APP_ENV = 'local'
$env:CONTROL_SYSTEM_IDENTITY_ADAPTER = 'genb'
$env:GENB_BASE_URL = 'http://127.0.0.1:8581'
$env:CONTROL_SYSTEM_INTERNAL_TOKEN = $internalToken
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = '6379'
$env:REDIS_PASSWORD = $redisMatch.Matches[0].Groups[1].Value
$env:REDIS_KEY_PEPPER = $internalToken
$env:RUNTIME_INFERENCE_BASE_URL = 'http://127.0.0.1:18704'
$env:CONTROL_SYSTEM_RUNTIME_TOKEN = $credential
$serviceDir = Join-Path $root 'control-system-service'
$env:PYTHONPATH = Join-Path $serviceDir 'src'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$logDir = Join-Path $root '.logs\customer-core-agent-local'
$process = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system.main:create_application', '--factory',
    '--host', '127.0.0.1', '--port', '18701'
) -WorkingDirectory $serviceDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'control-m3.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'control-m3.stderr.log') -PassThru

$deadline = (Get-Date).AddSeconds(30)
do {
    if ($process.HasExited) { throw "Control System进程已退出: $($process.ExitCode)" }
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:18701/health/ready' -TimeoutSec 2
        if ($health.status -eq 'UP') { break }
    } catch {
        $health = $null
    }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $deadline)
if (-not $health -or $health.status -ne 'UP') { throw 'Control System未就绪' }

[pscustomobject]@{ Pid = $process.Id; Status = $health.status; Port = $port }
