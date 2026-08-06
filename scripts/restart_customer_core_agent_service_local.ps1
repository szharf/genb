param(
    [Parameter(Mandatory = $true)][string]$RedisPassword,
    [int]$Port = 18714
)

$ErrorActionPreference = 'Stop'
$root = 'D:\code\opencode\genb'
$agentDir = Join-Path $root 'control-system-test-agent'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$credentialPath = Join-Path $root '.local-secrets\core-component-demo-agent.credential.dpapi'
$logDir = Join-Path $root '.logs\customer-core-agent-local'

if (-not (Test-Path -LiteralPath $credentialPath)) {
    throw 'Local protected customer agent credential does not exist'
}
$connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($connection) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
    if ($process.CommandLine -notlike '*control_system_test_agent.web*') {
        throw "Port $Port is owned by an unexpected process"
    }
    Stop-Process -Id $connection.OwningProcess -Force
}

$protected = (Get-Content -LiteralPath $credentialPath -Raw).Trim() | ConvertTo-SecureString
$env:SERVICE_CREDENTIAL = [Net.NetworkCredential]::new('', $protected).Password
$env:AGENT_ID = 'core-component-demo-agent'
$env:GENB_BASE_URL = 'http://127.0.0.1:8581/api'
$env:HTTP_TIMEOUT_SECONDS = '90'
$env:AGENT_REDIS_HOST = '127.0.0.1'
$env:AGENT_REDIS_PORT = '6379'
$env:AGENT_REDIS_PASSWORD = $RedisPassword
$env:CONTROL_SYSTEM_BASE_URL = 'http://127.0.0.1:18701'
$env:AGENT_CALLBACK_URL = 'http://localhost:18714/auth/callback'
$env:PORTAL_AGENT_SSO_URL = 'http://localhost:9100/agent-sso'
$env:PYTHONPATH = Join-Path $agentDir 'src'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system_test_agent.web:app', '--host', '127.0.0.1', '--port', "$Port"
) -WorkingDirectory $agentDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'agent.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'agent.stderr.log') | Out-Null

$deadline = (Get-Date).AddSeconds(20)
do {
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/live" -TimeoutSec 2 }
    catch { $health = $null }
    if ($health.status -eq 'UP') { break }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $deadline)
if ($health.status -ne 'UP') { throw 'Customer core agent did not become ready' }
Write-Output "customer-core-agent=UP port=$Port"
