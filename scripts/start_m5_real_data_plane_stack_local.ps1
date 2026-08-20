$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$gatewayPython = 'C:\Users\szhar\AppData\Local\Python\bin\python.exe'
$logDir = Join-Path $root '.logs\m5-real-gate'
$agentId = 'core-component-demo-agent'

function Read-ProtectedSecret([string]$Path) {
    $secure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

function Require-FreePort([int]$Port) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use"
    }
}

function Wait-Ready([string]$Url, [Diagnostics.Process]$Process, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        if ($Process.HasExited) { throw "Process $($Process.Id) exited with code $($Process.ExitCode): $Url" }
        try { $health = Invoke-RestMethod -Uri $Url -TimeoutSec 2 } catch { $health = $null }
        if ($health.status -in @('UP', 'ok', 'ready')) { return }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url"
}

if (-not (Get-NetTCPConnection -LocalPort 8581 -State Listen -ErrorAction SilentlyContinue)) {
    throw 'GenB must be running on 8581'
}
foreach ($port in 16380, 18080, 18081, 18702, 18704, 18705, 18712, 18714, 18716) {
    Require-FreePort $port
}
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$credential = Read-ProtectedSecret (Join-Path $root ".local-secrets\$agentId.credential.dpapi")
$internal = Read-ProtectedSecret (Join-Path $root '.local-secrets\genb-component-internal-token.dpapi')
$redisLine = Select-String -LiteralPath 'D:\environment\redis\redis.windows-service.conf' `
    -Pattern '^\s*requirepass\s+(\S+)' | Select-Object -First 1
$sharedRedisPassword = $redisLine.Matches[0].Groups[1].Value

$redis = Start-Process -FilePath 'D:\environment\redis\redis-server.exe' `
    -ArgumentList (Join-Path $root 'genb-data-plane-gateway\redis\local-gate-c.conf') `
    -WorkingDirectory (Join-Path $root 'genb-data-plane-gateway') -WindowStyle Hidden -PassThru
$deadline = (Get-Date).AddSeconds(15)
do { $redisReady = Test-NetConnection 127.0.0.1 -Port 16380 -InformationLevel Quiet; if (-not $redisReady) { Start-Sleep -Milliseconds 200 } } `
    while (-not $redisReady -and (Get-Date) -lt $deadline)
if (-not $redisReady) { throw 'Dedicated Redis did not become ready' }

$runtimeDir = Join-Path $root 'runtime-system-service'
$env:APP_ENV = 'local'; $env:RUNTIME_STATIC_TOKEN = $credential
Remove-Item Env:MODEL_ROUTING_CONFIG -ErrorAction SilentlyContinue
Remove-Item Env:RUNTIME_LOCAL_ENV_FILE -ErrorAction SilentlyContinue
Remove-Item Env:RUNTIME_FAKE_STRUCTURED_CONTENT -ErrorAction SilentlyContinue
$env:PYTHONPATH = Join-Path $runtimeDir 'src'
$runtime = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'runtime_system.main:app', '--host', '127.0.0.1', '--port', '18704'
) -WorkingDirectory $runtimeDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'runtime.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'runtime.stderr.log') -PassThru
Wait-Ready 'http://127.0.0.1:18704/health/ready' $runtime

$long = & (Join-Path $root 'scripts\start_long_term_memory_service_local.ps1')

$memoryDir = Join-Path $root 'short-term-memory-service'
$env:SHORT_TERM_MEMORY_STORE = 'redis'; $env:SHORT_TERM_MEMORY_REDIS_HOST = '127.0.0.1'
$env:SHORT_TERM_MEMORY_REDIS_PORT = '6379'; $env:SHORT_TERM_MEMORY_REDIS_PASSWORD = $sharedRedisPassword
$env:SHORT_TERM_MEMORY_AUTH_MODE = 'genb'; $env:SHORT_TERM_MEMORY_GENB_URL = 'http://127.0.0.1:8581/api'
$env:SHORT_TERM_MEMORY_GENB_INTERNAL_TOKEN = $internal; $env:PYTHONPATH = Join-Path $memoryDir 'src'
$short = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'short_term_memory.main:app', '--host', '127.0.0.1', '--port', '18705'
) -WorkingDirectory $memoryDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'short.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'short.stderr.log') -PassThru
Wait-Ready 'http://127.0.0.1:18705/health/ready' $short

$application = Get-Content -LiteralPath (Join-Path $root 'gen-b\gen-b-backend\src\main\resources\application.yml') -Raw
$dbUser = [regex]::Match($application, 'GENB_DB_USERNAME:([^}]+)').Groups[1].Value.Trim()
$dbPassword = [regex]::Match($application, 'GENB_DB_PASSWORD:([^}]+)').Groups[1].Value.Trim()
$planningDir = Join-Path $root 'planning-reasoning-service'
$env:PLANNING_REASONING_POSTGRES_DSN = "host=127.0.0.1 port=5432 dbname=genb_local user=$dbUser password=$dbPassword sslmode=disable options='-c search_path=bank_agent_db'"
$env:PLANNING_REASONING_AUTH_MODE = 'genb'; $env:PLANNING_REASONING_GENB_URL = 'http://127.0.0.1:8581/api'
$env:PLANNING_REASONING_GENB_INTERNAL_TOKEN = $internal
$env:PLANNING_REASONING_INFERENCE_URL = 'http://127.0.0.1:18704'
$env:PLANNING_REASONING_MODEL_ALIAS = 'planning-authoring-default'
$env:PLANNING_REASONING_ANALYSIS_MODEL_ALIAS = 'planning-analysis-default'
$env:PYTHONPATH = Join-Path $planningDir 'src'
& $python (Join-Path $planningDir 'scripts\apply_migrations.py') | Out-Null
$planning = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'planning_reasoning.main:app', '--host', '127.0.0.1', '--port', '18712'
) -WorkingDirectory $planningDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'planning.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'planning.stderr.log') -PassThru
Wait-Ready 'http://127.0.0.1:18712/health/ready' $planning

$agentDir = Join-Path $root 'control-system-test-agent'
$env:AGENT_ID = $agentId; $env:GENB_BASE_URL = 'http://127.0.0.1:8581/api'
$env:SERVICE_CREDENTIAL = $credential; $env:HTTP_TIMEOUT_SECONDS = '30'
$env:DATA_PLANE_GATEWAY_URL = 'http://127.0.0.1:18080'
$env:AGENT_REDIS_HOST = '127.0.0.1'; $env:AGENT_REDIS_PORT = '16380'; $env:AGENT_REDIS_PASSWORD = ''
$env:PYTHONPATH = Join-Path $agentDir 'src'
$agent = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system_test_agent.web:app', '--host', '127.0.0.1', '--port', '18714'
) -WorkingDirectory $agentDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'agent.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'agent.stderr.log') -PassThru
Wait-Ready 'http://127.0.0.1:18714/health/live' $agent

$gatewayDir = Join-Path $root 'genb-data-plane-gateway'
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
$gateway = Start-Process -FilePath $gatewayPython -ArgumentList @('-m', 'genb_gateway.server') `
    -WorkingDirectory $gatewayDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'gateway.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'gateway.stderr.log') -PassThru
Wait-Ready 'http://127.0.0.1:18080/health/ready' $gateway

if (-not $env:GENB_LOCAL_JWT_SECRET) {
    throw '请先通过本地安全配置设置 GENB_LOCAL_JWT_SECRET，脚本不提供固定Secret。'
}
$env:GENB_BASE_URL = 'http://127.0.0.1:8581/api'
$portal = Start-Process -FilePath $gatewayPython -ArgumentList @('tests\m5_real_portal.py') `
    -WorkingDirectory $gatewayDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'portal.stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'portal.stderr.log') -PassThru
$deadline = (Get-Date).AddSeconds(15)
do { $portalReady = Test-NetConnection 127.0.0.1 -Port 18716 -InformationLevel Quiet; if (-not $portalReady) { Start-Sleep -Milliseconds 200 } } `
    while (-not $portalReady -and (Get-Date) -lt $deadline)
if (-not $portalReady) { throw 'Local portal fixture did not become ready' }

& 'D:\JAVA\tool\nginx-1.31.3\nginx.exe' -p 'D:\JAVA\tool\nginx-1.31.3' `
    -c 'D:/code/opencode/genb/genb-data-plane-gateway/nginx/genb-gateway.local.conf'
$deadline = (Get-Date).AddSeconds(15)
do { $nginxReady = Test-NetConnection 127.0.0.1 -Port 18081 -InformationLevel Quiet; if (-not $nginxReady) { Start-Sleep -Milliseconds 200 } } `
    while (-not $nginxReady -and (Get-Date) -lt $deadline)
if (-not $nginxReady) { throw 'Nginx did not become ready' }

[pscustomobject]@{
    Redis = $redis.Id; Runtime = $runtime.Id; LongTerm = $long.Pid; ShortTerm = $short.Id
    Planning = $planning.Id; Agent = $agent.Id; Gateway = $gateway.Id; Portal = $portal.Id
}
