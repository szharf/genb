$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$logDir = Join-Path $root '.logs\customer-core-agent-local'

function Read-ProtectedSecret([string]$Path) {
    $secure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

function Stop-ExpectedService([int]$Port, [string]$CommandPattern) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $listener) { return }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($process.CommandLine -notlike "*$CommandPattern*") {
        throw "端口$Port不是预期服务，拒绝重启"
    }
    Stop-Process -Id $listener.OwningProcess -Force
}

function Wait-Ready([string]$Url) {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        try {
            $health = Invoke-RestMethod -Uri $Url -TimeoutSec 2
            if ($health.status -in @('UP', 'ready', 'ok')) { return }
        } catch {
            $health = $null
        }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    throw "服务未就绪: $Url"
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$internalToken = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\genb-component-internal-token.dpapi'
)
$redisMatch = Select-String -LiteralPath 'D:\environment\redis\redis.windows-service.conf' `
    -Pattern '^\s*requirepass\s+(\S+)' | Select-Object -First 1
if (-not $redisMatch) { throw 'Redis密码配置缺失' }
$redisPassword = $redisMatch.Matches[0].Groups[1].Value

Stop-ExpectedService 18705 'short_term_memory.main:app'
$memoryDir = Join-Path $root 'short-term-memory-service'
$env:SHORT_TERM_MEMORY_STORE = 'redis'
$env:SHORT_TERM_MEMORY_REDIS_HOST = '127.0.0.1'
$env:SHORT_TERM_MEMORY_REDIS_PORT = '6379'
$env:SHORT_TERM_MEMORY_REDIS_PASSWORD = $redisPassword
$env:SHORT_TERM_MEMORY_AUTH_MODE = 'genb'
$env:SHORT_TERM_MEMORY_GENB_URL = 'http://127.0.0.1:8581/api'
$env:SHORT_TERM_MEMORY_GENB_INTERNAL_TOKEN = $internalToken
$env:PYTHONPATH = Join-Path $memoryDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'short_term_memory.main:app', '--host', '127.0.0.1', '--port', '18705'
) -WorkingDirectory $memoryDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'short-memory-prem5.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'short-memory-prem5.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18705/health/ready'

Stop-ExpectedService 18712 'planning_reasoning.main:app'
$application = Get-Content -LiteralPath (
    Join-Path $root 'gen-b\gen-b-backend\src\main\resources\application.yml'
) -Raw
$dbUser = [regex]::Match($application, 'GENB_DB_USERNAME:([^}]+)').Groups[1].Value.Trim()
$dbPassword = [regex]::Match($application, 'GENB_DB_PASSWORD:([^}]+)').Groups[1].Value.Trim()
$planningDir = Join-Path $root 'planning-reasoning-service'
$env:PLANNING_REASONING_POSTGRES_DSN = `
    "host=127.0.0.1 port=5432 dbname=genb_local user=$dbUser password=$dbPassword sslmode=disable options='-c search_path=bank_agent_db'"
$env:PLANNING_REASONING_AUTH_MODE = 'genb'
$env:PLANNING_REASONING_GENB_URL = 'http://127.0.0.1:8581/api'
$env:PLANNING_REASONING_GENB_INTERNAL_TOKEN = $internalToken
$env:PLANNING_REASONING_INFERENCE_URL = 'http://127.0.0.1:18704'
$env:PLANNING_REASONING_MODEL_ALIAS = 'planning-authoring-default'
$env:PLANNING_REASONING_ANALYSIS_MODEL_ALIAS = 'planning-analysis-default'
$env:PYTHONPATH = Join-Path $planningDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'planning_reasoning.main:app', '--host', '127.0.0.1', '--port', '18712'
) -WorkingDirectory $planningDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'planning-prem5.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'planning-prem5.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18712/health/ready'

[pscustomobject]@{
    ShortTermMemory = Invoke-RestMethod 'http://127.0.0.1:18705/version'
    PlanningReasoning = Invoke-RestMethod 'http://127.0.0.1:18712/version'
}
