param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$root = 'D:\code\opencode\genb'
$python = Join-Path $root 'gen-o\backend\.venv\Scripts\python.exe'

function Resolve-SpringDefault([string]$Raw) {
    $value = $Raw.Trim()
    if ($value -match '^\$\{([^:}]+):(.*)\}$') {
        $configured = [Environment]::GetEnvironmentVariable($Matches[1])
        if ($configured) { return $configured }
        return $Matches[2]
    }
    return $value
}

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
$env:LOCAL_GENB_POSTGRES_DSN = (
    "host=$dbHost port=$dbPort dbname=$dbName user=$dbUser password=$dbPassword"
)
$arguments = @(
    (Join-Path $root 'long-term-memory-service\scripts\switch_genb_binding_local.py')
)
if ($Apply) { $arguments += '--apply' }
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "本地LONG_TERM_MEMORY绑定切换失败，退出码 $LASTEXITCODE"
}
