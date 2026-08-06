param([int]$RuntimePort = 18704)

$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$serviceDir = Join-Path $root 'long-term-memory-service'
$logDir = Join-Path $root '.logs\long-term-memory-service'

function Read-ProtectedSecret([string]$Path) {
    $encrypted = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secure = $encrypted | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

function Resolve-SpringDefault([string]$Raw) {
    $value = $Raw.Trim()
    if ($value -match '^\$\{([^:}]+):(.*)\}$') {
        $configured = [Environment]::GetEnvironmentVariable($Matches[1])
        if ($configured) { return $configured }
        return $Matches[2]
    }
    return $value
}

function Wait-Ready([string]$Url, [Diagnostics.Process]$Process) {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        if ($Process.HasExited) {
            throw "Long-term Memory进程已退出，退出码 $($Process.ExitCode)"
        }
        try {
            $health = Invoke-RestMethod -Uri $Url -TimeoutSec 2
            if ($health.status -eq 'UP') { return $health }
        }
        catch {
            $health = $null
        }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    throw "Long-term Memory未就绪: $Url"
}

if (Get-NetTCPConnection -State Listen -LocalPort 18702 -ErrorAction SilentlyContinue) {
    throw '端口18702已被占用'
}
if (-not (Get-NetTCPConnection -State Listen -LocalPort 8581 -ErrorAction SilentlyContinue)) {
    throw '本地GenB 8581未启动'
}
if (-not (Get-NetTCPConnection -State Listen -LocalPort $RuntimePort -ErrorAction SilentlyContinue)) {
    throw "本地Runtime Inference $RuntimePort 未启动"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$credential = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\core-component-demo-agent.credential.dpapi'
)
$internalToken = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\genb-component-internal-token.dpapi'
)

$application = Get-Content -LiteralPath (
    Join-Path $root 'gen-b\gen-b-backend\src\main\resources\application.yml'
) -Encoding UTF8
$urlIndex = -1
for ($index = 0; $index -lt $application.Count; $index++) {
    if ($application[$index] -match '^\s*url:\s*.*jdbc:postgresql://') {
        $urlIndex = $index
        break
    }
}
if ($urlIndex -lt 0) { throw '无法定位本地PostgreSQL datasource' }
$jdbc = Resolve-SpringDefault ($application[$urlIndex] -replace '^\s*url:\s*', '')
$dbUser = Resolve-SpringDefault ($application[$urlIndex + 1] -replace '^\s*username:\s*', '')
$dbPassword = Resolve-SpringDefault ($application[$urlIndex + 2] -replace '^\s*password:\s*', '')
if ($jdbc -notmatch '^jdbc:postgresql://([^:/]+):(\d+)/([^?\s]+)') {
    throw '无法解析本地PostgreSQL地址'
}
$dbHost = $Matches[1]
$dbPort = $Matches[2]
$dbName = $Matches[3]
if ($dbHost -notin @('localhost', '127.0.0.1', '::1')) {
    throw '拒绝非本地PostgreSQL地址'
}

$env:LONG_TERM_MEMORY_POSTGRES_DSN = (
    "host=$dbHost port=$dbPort dbname=$dbName user=$dbUser password=$dbPassword"
)
$env:LONG_TERM_MEMORY_AUTO_MIGRATE = 'true'
$env:LONG_TERM_MEMORY_AUTH_MODE = 'genb'
$env:LONG_TERM_MEMORY_GENB_URL = 'http://127.0.0.1:8581/api'
$env:LONG_TERM_MEMORY_GENB_INTERNAL_TOKEN = $internalToken
$env:LONG_TERM_MEMORY_RUNTIME_TOKEN = $credential
$env:LONG_TERM_MEMORY_RUNTIME_URL = (
    "http://127.0.0.1:$RuntimePort/api/v1/runtime-system/inference"
)
$env:LONG_TERM_MEMORY_MODEL_ALIAS = 'memory-extraction-default'
$env:PYTHONPATH = Join-Path $serviceDir 'src'

$process = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'long_term_memory.main:app',
    '--host', '127.0.0.1', '--port', '18702'
) -WorkingDirectory $serviceDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'stderr.log') -PassThru
$health = Wait-Ready 'http://127.0.0.1:18702/health/ready' $process

[pscustomobject]@{
    Pid = $process.Id
    Status = $health.status
    Store = $health.store
    Url = 'http://127.0.0.1:18702'
}
