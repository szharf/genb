$ErrorActionPreference = 'Stop'

$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'

function Read-ProtectedSecret([string]$Path) {
    $encrypted = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secure = $encrypted | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

if (-not (Get-NetTCPConnection -State Listen -LocalPort 18702 -ErrorAction SilentlyContinue)) {
    throw '本地Long-term Memory 18702未启动'
}

$redisMatch = Select-String -LiteralPath `
    'D:\environment\redis\redis.windows-service.conf' `
    -Pattern '^\s*requirepass\s+(\S+)' | Select-Object -First 1
if (-not $redisMatch) { throw '本地Redis密码未配置' }

$env:LOCAL_REDIS_PASSWORD = $redisMatch.Matches[0].Groups[1].Value
$env:LOCAL_AGENT_CREDENTIAL = Read-ProtectedSecret (
    Join-Path $root '.local-secrets\core-component-demo-agent.credential.dpapi'
)
$env:GENB_BASE_URL = 'http://127.0.0.1:8581/api'
$env:LONG_TERM_MEMORY_BASE_URL = 'http://127.0.0.1:18702'
$env:PYTHONPATH = @(
    (Join-Path $root 'long-term-memory-service\src'),
    (Join-Path $root 'control-system-test-agent\src')
) -join ';'

& $python (
    Join-Path $root 'long-term-memory-service\scripts\accept_formal_local.py'
)
if ($LASTEXITCODE -ne 0) {
    throw "Long-term Memory正式本地验收失败，退出码 $LASTEXITCODE"
}
