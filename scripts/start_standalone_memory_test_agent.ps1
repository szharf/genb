param(
    [string]$Username = 'admin',
    [Parameter(Mandatory = $true)][string]$Password,
    [switch]$CredentialFromEnvironment
)

$ErrorActionPreference = 'Stop'
$agentId = 'standalone-memory-test-agent'
$backendUrl = 'http://127.0.0.1:8581/api'
$agentPort = 18711
$projectDir = 'D:\code\opencode\genb\control-system-test-agent'
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
$logDir = 'D:\code\opencode\genb\.logs\core-memory-local'

$existing = Get-NetTCPConnection -State Listen -LocalPort $agentPort -ErrorAction SilentlyContinue
if ($existing) {
    $existingProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($existing.OwningProcess)"
    if ($existingProcess.CommandLine -notlike '*control_system_test_agent.web*') {
        throw "Port $agentPort is owned by an unexpected process"
    }
    Stop-Process -Id $existing.OwningProcess -Force
}

$login = Invoke-RestMethod -Method Post -Uri "$backendUrl/v1/auth/login" `
    -ContentType 'application/json' `
    -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)
$token = $login.data.token
$secret = $env:SERVICE_CREDENTIAL
if (-not $CredentialFromEnvironment) {
    $issued = Invoke-RestMethod -Method Post -Uri "$backendUrl/v1/service-credentials" `
        -Headers @{ Authorization = "Bearer $token" } `
        -ContentType 'application/json' `
        -Body (@{ agentId = $agentId; name = 'Standalone memory test agent runtime' } | ConvertTo-Json)
    $secret = $issued.data.credentialSecret
}
if (-not $secret) {
    throw 'Credential issuance did not return a secret'
}

$env:AGENT_ID = $agentId
$env:GENB_BASE_URL = $backendUrl
$env:SERVICE_CREDENTIAL = $secret
$env:PYTHONPATH = "$projectDir\src"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'control_system_test_agent.web:app', '--host', '127.0.0.1', '--port', "$agentPort" `
    -WorkingDirectory $projectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\standalone-memory-test-agent.stdout.log" `
    -RedirectStandardError "$logDir\standalone-memory-test-agent.stderr.log"

Invoke-RestMethod -Method Put -Uri "$backendUrl/v1/agents/$agentId" `
    -Headers @{ Authorization = "Bearer $token" } `
    -ContentType 'application/json' `
    -Body (@{
        port = $agentPort
        host = '127.0.0.1'
        workDirectory = $projectDir
        startCommand = 'python -m uvicorn control_system_test_agent.web:app --host 127.0.0.1 --port 18711'
    } | ConvertTo-Json) | Out-Null

$deadline = (Get-Date).AddSeconds(20)
do {
    try {
        $health = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$agentPort/health/live" -TimeoutSec 2
        if ($health.StatusCode -eq 200) { break }
    } catch {
        $health = $null
    }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

if (-not $health -or $health.StatusCode -ne 200) {
    throw 'Test agent did not become healthy'
}

Write-Output "standalone-memory-test-agent started on $agentPort; credential kept only in process environment"
