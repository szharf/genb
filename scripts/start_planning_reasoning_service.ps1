param(
    [int]$Port = 18712,
    [ValidateSet('development_headers', 'genb')][string]$AuthMode = 'development_headers',
    [switch]$UseLocalGenB
)

$ErrorActionPreference = 'Stop'
$projectDir = 'D:\code\opencode\genb\planning-reasoning-service'
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
$logDir = 'D:\code\opencode\genb\.logs\planning-reasoning-local'

if ($UseLocalGenB) {
    $backendConfig = Get-Content -LiteralPath 'D:\code\opencode\genb\gen-b\gen-b-backend\src\main\resources\application.yml' -Raw
    $userMatch = [regex]::Match($backendConfig, 'GENB_DB_USERNAME:([^}]+)')
    $passwordMatch = [regex]::Match($backendConfig, 'GENB_DB_PASSWORD:([^}]+)')
    $dbUser = if ($userMatch.Success) { $userMatch.Groups[1].Value.Trim() } else { [regex]::Match($backendConfig, 'username:\s+([^\r\n]+)').Groups[1].Value.Trim() }
    $env:PGPASSWORD = if ($passwordMatch.Success) { $passwordMatch.Groups[1].Value.Trim() } else { [regex]::Match($backendConfig, 'password:\s+([^\r\n]+)').Groups[1].Value.Trim() }
    $env:PLANNING_REASONING_POSTGRES_DSN = "host=127.0.0.1 port=5432 dbname=genb_local user=$dbUser sslmode=disable options='-c search_path=bank_agent_db'"
    $protectedToken = (Get-Content -LiteralPath 'D:\code\opencode\genb\.local-secrets\genb-component-internal-token.dpapi' -Raw).Trim() |
        ConvertTo-SecureString
    $env:PLANNING_REASONING_GENB_INTERNAL_TOKEN = [Net.NetworkCredential]::new('', $protectedToken).Password
    $env:PLANNING_REASONING_GENB_URL = 'http://127.0.0.1:8581/api'
    $env:PLANNING_REASONING_INFERENCE_URL = 'http://127.0.0.1:18704'
    $env:PLANNING_REASONING_MODEL_ALIAS = 'planning-authoring-default'
    $env:PLANNING_REASONING_ANALYSIS_MODEL_ALIAS = 'planning-analysis-default'
}

if (-not $env:PLANNING_REASONING_POSTGRES_DSN) {
    throw 'PLANNING_REASONING_POSTGRES_DSN must be provided through the process environment or secret manager'
}
if ($AuthMode -eq 'genb' -and -not $env:PLANNING_REASONING_GENB_INTERNAL_TOKEN) {
    throw 'PLANNING_REASONING_GENB_INTERNAL_TOKEN is required in genb auth mode'
}

$existing = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($existing.OwningProcess)"
    if ($process.CommandLine -notlike '*planning_reasoning.main*') {
        throw "Port $Port is owned by an unexpected process"
    }
    Stop-Process -Id $existing.OwningProcess -Force
}

$env:PLANNING_REASONING_AUTH_MODE = $AuthMode
$env:PYTHONPATH = "$projectDir\src"
& $python "$projectDir\scripts\apply_migrations.py"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'planning_reasoning.main:app', '--host', '127.0.0.1', '--port', "$Port" `
    -WorkingDirectory $projectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\planning-reasoning.stdout.log" `
    -RedirectStandardError "$logDir\planning-reasoning.stderr.log"

$deadline = (Get-Date).AddSeconds(20)
do {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/ready" -TimeoutSec 2
        if ($health.status -eq 'UP') { break }
    } catch {
        $health = $null
    }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

if (-not $health -or $health.status -ne 'UP') {
    throw 'Planning and reasoning service did not become ready'
}

Write-Output "planning-reasoning-service started on $Port with store=$($health.store)"
