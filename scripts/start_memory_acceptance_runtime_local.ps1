$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'
$runtimeDir = Join-Path $root 'long-term-memory-service'
$logDir = Join-Path $root '.logs\memory-acceptance-runtime'

if (Get-NetTCPConnection -State Listen -LocalPort 18706 -ErrorAction SilentlyContinue) {
    throw '端口18706已被占用'
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$env:APP_ENV = 'local'
$env:PYTHONPATH = Join-Path $runtimeDir 'src'
$process = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'long_term_memory.acceptance_runtime:app',
    '--host', '127.0.0.1', '--port', '18706'
) -WorkingDirectory $runtimeDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'stdout.log') `
    -RedirectStandardError (Join-Path $logDir 'stderr.log') -PassThru

$deadline = (Get-Date).AddSeconds(30)
do {
    if ($process.HasExited) {
        throw "验收Runtime进程已退出，退出码 $($process.ExitCode)"
    }
    try {
        $response = Invoke-WebRequest -UseBasicParsing `
            -Uri 'http://127.0.0.1:18706/health/live' -TimeoutSec 2
        if ($response.StatusCode -eq 200) { break }
    }
    catch {
        $response = $null
    }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $deadline)
if (-not $response -or $response.StatusCode -ne 200) {
    throw '验收Runtime 18706未就绪'
}

[pscustomobject]@{ Pid = $process.Id; Status = 'UP'; Url = 'http://127.0.0.1:18706' }
