$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$backendUrl = 'http://127.0.0.1:8581/api'
$logDir = Join-Path $root '.logs\customer-core-agent-local'

function Read-ProtectedSecret([string]$Path) {
    $encrypted = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secure = $encrypted | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

function Wait-Ready([string]$Url, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $health = Invoke-RestMethod -Uri $Url -TimeoutSec 2
            if ($health.status -in @('UP', 'ok', 'ready')) { return }
        } catch {
            $health = $null
        }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url"
}

function Require-FreePort([int]$Port) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use"
    }
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
if (-not (Get-NetTCPConnection -State Listen -LocalPort 8581 -ErrorAction SilentlyContinue)) {
    throw 'GenB backend must be running on port 8581'
}

$credential = Read-ProtectedSecret (Join-Path $root '.local-secrets\core-component-demo-agent.credential.dpapi')
$internalToken = Read-ProtectedSecret (Join-Path $root '.local-secrets\genb-component-internal-token.dpapi')
$redisMatch = Select-String -LiteralPath 'D:\environment\redis\redis.windows-service.conf' `
    -Pattern '^\s*requirepass\s+(\S+)' | Select-Object -First 1
if (-not $redisMatch) { throw 'Redis requirepass is not configured' }
$redisPassword = $redisMatch.Matches[0].Groups[1].Value

$application = Get-Content -LiteralPath `
    (Join-Path $root 'gen-b\gen-b-backend\src\main\resources\application.yml') -Raw
$userMatch = [regex]::Match($application, 'GENB_DB_USERNAME:([^}]+)')
$passwordMatch = [regex]::Match($application, 'GENB_DB_PASSWORD:([^}]+)')
$dbUser = if ($env:GENB_DB_USERNAME) { $env:GENB_DB_USERNAME } `
    elseif ($userMatch.Success) { $userMatch.Groups[1].Value.Trim() } `
    else { [regex]::Match($application, 'username:\s+([^\r\n]+)').Groups[1].Value.Trim() }
$dbPassword = if ($env:GENB_DB_PASSWORD) { $env:GENB_DB_PASSWORD } `
    elseif ($passwordMatch.Success) { $passwordMatch.Groups[1].Value.Trim() } `
    else { [regex]::Match($application, 'password:\s+([^\r\n]+)').Groups[1].Value.Trim() }

Require-FreePort 18704
$runtimeDir = Join-Path $root 'runtime-system-service'
$env:APP_ENV = 'local'
$env:RUNTIME_STATIC_TOKEN = $credential
$env:RUNTIME_LOCAL_ENV_FILE = Join-Path $root 'C01智能审单专家智能体\.env'
$env:MODEL_ROUTING_CONFIG = Join-Path $runtimeDir 'config\model-routing.deepseek.json'
$env:PYTHONPATH = Join-Path $runtimeDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'runtime_system.main:app', '--host', '127.0.0.1', '--port', '18704'
) -WorkingDirectory $runtimeDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'runtime-sso.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'runtime-sso.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18704/health/ready'

Require-FreePort 18702
& (Join-Path $root 'scripts\start_long_term_memory_service_local.ps1') | Out-Null
Wait-Ready 'http://127.0.0.1:18702/health/ready'

Require-FreePort 18701
$controlDir = Join-Path $root 'control-system-service'
$env:APP_ENV = 'local'
$env:CONTROL_SYSTEM_IDENTITY_ADAPTER = 'genb'
$env:GENB_BASE_URL = 'http://127.0.0.1:8581'
$env:CONTROL_SYSTEM_INTERNAL_TOKEN = $internalToken
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = '6379'
$env:REDIS_PASSWORD = $redisPassword
$env:REDIS_KEY_PEPPER = $internalToken
$env:RUNTIME_INFERENCE_BASE_URL = 'http://127.0.0.1:18704'
$env:CONTROL_SYSTEM_RUNTIME_TOKEN = $credential
$env:PYTHONPATH = Join-Path $controlDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system.main:create_application', '--factory', '--host', '127.0.0.1', '--port', '18701'
) -WorkingDirectory $controlDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'control-sso.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'control-sso.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18701/health/ready'

Require-FreePort 18705
$memoryDir = Join-Path $root 'short-term-memory-service'
$env:SHORT_TERM_MEMORY_STORE = 'redis'
$env:SHORT_TERM_MEMORY_REDIS_HOST = '127.0.0.1'
$env:SHORT_TERM_MEMORY_REDIS_PORT = '6379'
$env:SHORT_TERM_MEMORY_REDIS_PASSWORD = $redisPassword
$env:SHORT_TERM_MEMORY_AUTH_MODE = 'genb'
$env:SHORT_TERM_MEMORY_GENB_URL = $backendUrl
$env:SHORT_TERM_MEMORY_GENB_INTERNAL_TOKEN = $internalToken
$env:PYTHONPATH = Join-Path $memoryDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'short_term_memory.main:app', '--host', '127.0.0.1', '--port', '18705'
) -WorkingDirectory $memoryDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'short-memory-sso.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'short-memory-sso.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18705/health/ready'

Require-FreePort 18712
$planningDir = Join-Path $root 'planning-reasoning-service'
$env:PLANNING_REASONING_POSTGRES_DSN = `
    "host=127.0.0.1 port=5432 dbname=genb_local user=$dbUser password=$dbPassword sslmode=disable options='-c search_path=bank_agent_db'"
$env:PLANNING_REASONING_AUTH_MODE = 'genb'
$env:PLANNING_REASONING_GENB_URL = $backendUrl
$env:PLANNING_REASONING_GENB_INTERNAL_TOKEN = $internalToken
$env:PLANNING_REASONING_INFERENCE_URL = 'http://127.0.0.1:18704'
$env:PLANNING_REASONING_MODEL_ALIAS = 'planning-authoring-default'
$env:PLANNING_REASONING_ANALYSIS_MODEL_ALIAS = 'planning-analysis-default'
$env:PYTHONPATH = Join-Path $planningDir 'src'
& $python (Join-Path $planningDir 'scripts\apply_migrations.py') | Out-Null
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'planning_reasoning.main:app', '--host', '127.0.0.1', '--port', '18712'
) -WorkingDirectory $planningDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'planning-sso.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'planning-sso.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18712/health/ready'

Require-FreePort 18714
$agentDir = Join-Path $root 'control-system-test-agent'
$env:AGENT_ID = 'core-component-demo-agent'
$env:GENB_BASE_URL = $backendUrl
$env:SERVICE_CREDENTIAL = $credential
$env:HTTP_TIMEOUT_SECONDS = '90'
$env:AGENT_REDIS_HOST = '127.0.0.1'
$env:AGENT_REDIS_PORT = '6379'
$env:AGENT_REDIS_PASSWORD = $redisPassword
$env:CONTROL_SYSTEM_BASE_URL = 'http://127.0.0.1:18701'
$env:AGENT_CALLBACK_URL = 'http://localhost:18714/auth/callback'
$env:PORTAL_AGENT_SSO_URL = 'http://localhost:9100/agent-sso'
$env:PYTHONPATH = Join-Path $agentDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system_test_agent.web:app', '--host', '127.0.0.1', '--port', '18714'
) -WorkingDirectory $agentDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'agent-sso.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'agent-sso.stderr.log') | Out-Null
Wait-Ready 'http://127.0.0.1:18714/health/live'

Write-Output 'Customer core agent services ready: 18701,18702,18704,18705,18712,18714'
