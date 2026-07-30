param(
    [string]$PrivateEnvFile = 'D:\code\opencode\genb\C01智能审单专家智能体\.env',
    [int]$Port = 18704
)

$ErrorActionPreference = 'Stop'
$root = 'D:\code\opencode\genb'
$runtimeDir = Join-Path $root 'runtime-system-service'
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
$logDir = Join-Path $root '.logs\runtime-model-live'
$tokenBytes = New-Object byte[] 32
$generator = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($tokenBytes) } finally { $generator.Dispose() }
$localToken = [Convert]::ToBase64String($tokenBytes)

$connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($connection) { throw "Port $Port is already in use" }
if (-not (Test-Path -LiteralPath $PrivateEnvFile -PathType Leaf)) {
    throw "Private model environment file does not exist"
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$env:APP_ENV = 'local'
$env:RUNTIME_STATIC_TOKEN = $localToken
$env:RUNTIME_LOCAL_ENV_FILE = $PrivateEnvFile
$env:MODEL_ROUTING_CONFIG = Join-Path $runtimeDir 'config\model-routing.deepseek.json'
$env:PYTHONPATH = Join-Path $runtimeDir 'src'
$process = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'runtime_system.main:app', '--host', '127.0.0.1', '--port', "$Port"
) -WorkingDirectory $runtimeDir -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $logDir 'runtime.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'runtime.stderr.log')

try {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/ready" -TimeoutSec 2
            if ($health.status -eq 'UP') { break }
        } catch { }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    if ($health.status -ne 'UP') { throw 'Runtime model service did not become ready' }

    $response = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:$Port/api/v1/runtime-system/inference" `
        -Headers @{ Authorization = "Bearer $localToken"; 'X-Request-Id' = 'req_runtime_live_acceptance' } `
        -ContentType 'application/json' `
        -Body (@{
            capability = 'CHAT'
            modelAlias = 'agent-chat-default'
            messages = @(
                @{ role = 'system'; content = '你是验收助手，只用一句中文回答。' },
                @{ role = 'user'; content = '请回答：真实模型调用成功。' }
            )
        } | ConvertTo-Json -Depth 20)

    [pscustomobject]@{
        status = 'PASS'
        provider = $response.data.provider
        model = $response.data.model
        inputTokens = $response.data.usage.inputTokens
        outputTokens = $response.data.usage.outputTokens
        requestId = $response.meta.requestId
        contentPresent = -not [string]::IsNullOrWhiteSpace($response.data.content)
    } | ConvertTo-Json -Compress
} finally {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    Remove-Item Env:RUNTIME_STATIC_TOKEN -ErrorAction SilentlyContinue
}
