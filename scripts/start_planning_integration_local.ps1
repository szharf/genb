param(
    [Parameter(Mandatory = $true)][string]$Password,
    [Parameter(Mandatory = $true)][string]$RedisPassword,
    [string]$Username = 'admin',
    [switch]$RotateAgentCredential
)

$ErrorActionPreference = 'Stop'
$root = 'D:\code\opencode\genb'
$backendDir = Join-Path $root 'gen-b\gen-b-backend'
$planningDir = Join-Path $root 'planning-reasoning-service'
$agentDir = Join-Path $root 'control-system-test-agent'
$memoryDir = Join-Path $root 'short-term-memory-service'
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
$maven = 'D:\environment\maven\apache-maven-3.6.3\bin\mvn.cmd'
$secretDir = Join-Path $root '.local-secrets'
$logDir = Join-Path $root '.logs\planning-integration-local'
$backendUrl = 'http://127.0.0.1:8581/api'
$agentId = 'standalone-planning-test-agent'

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Save-ProtectedSecret([string]$Path, [string]$Value) {
    ConvertTo-SecureString $Value -AsPlainText -Force |
        ConvertFrom-SecureString |
        Set-Content -LiteralPath $Path -Encoding ASCII
}

function Read-ProtectedSecret([string]$Path) {
    $encrypted = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secure = $encrypted | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

function Stop-LocalPort([int]$Port, [string]$Expected) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $connection) { return }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
    if ($process.CommandLine -notlike "*$Expected*") {
        throw "Port $Port is owned by an unexpected process"
    }
    Stop-Process -Id $connection.OwningProcess -Force
}

function Wait-Url([string]$Url, [int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url"
}

function Invoke-GenB([string]$Method, [string]$Path, $Body = $null) {
    $parameters = @{
        Method = $Method
        Uri = "$backendUrl$Path"
        Headers = @{ Authorization = "Bearer $script:token" }
        ContentType = 'application/json; charset=utf-8'
    }
    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 100
        $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
    }
    $response = Invoke-RestMethod @parameters
    if ($response.code -ne 200) { throw "GenB request failed: $Path" }
    return $response.data
}

New-Item -ItemType Directory -Path $secretDir, $logDir -Force | Out-Null
$internalSecretPath = Join-Path $secretDir 'genb-component-internal-token.dpapi'
if (Test-Path $internalSecretPath) {
    $internalToken = Read-ProtectedSecret $internalSecretPath
} else {
    $internalToken = New-RandomSecret
    Save-ProtectedSecret $internalSecretPath $internalToken
}

$application = Get-Content -LiteralPath (Join-Path $backendDir 'src\main\resources\application.yml') -Raw
$userMatch = [regex]::Match($application, 'GENB_DB_USERNAME:([^}]+)')
$passwordMatch = [regex]::Match($application, 'GENB_DB_PASSWORD:([^}]+)')
$dbUser = if ($env:GENB_DB_USERNAME) { $env:GENB_DB_USERNAME } elseif ($userMatch.Success) { $userMatch.Groups[1].Value.Trim() } else { [regex]::Match($application, 'username:\s+([^\r\n]+)').Groups[1].Value.Trim() }
$dbPassword = if ($env:GENB_DB_PASSWORD) { $env:GENB_DB_PASSWORD } elseif ($passwordMatch.Success) { $passwordMatch.Groups[1].Value.Trim() } else { [regex]::Match($application, 'password:\s+([^\r\n]+)').Groups[1].Value.Trim() }
$env:GENB_DB_URL = 'jdbc:postgresql://127.0.0.1:5432/genb_local?currentSchema=bank_agent_db&sslmode=disable'
$env:GENB_DB_USERNAME = $dbUser
$env:GENB_DB_PASSWORD = $dbPassword

Stop-LocalPort 8581 'GenBConsoleApplication'
Stop-LocalPort 18712 'planning_reasoning.main'
Stop-LocalPort 18713 'control_system_test_agent.web'
Stop-LocalPort 18705 'short_term_memory.main'

$env:CONTROL_SYSTEM_INTERNAL_TOKEN = $internalToken
$env:COMPONENT_ACTOR_KEY_ID = 'genb-local-planning'
$env:COMPONENT_ACTOR_PRIVATE_KEY_PATH = Join-Path $backendDir 'local-iteration11-actor.pem'
$env:GENB_TENANT_ID = 'genb-local'
$backendBuild = Join-Path $root '.tmp\genb-backend-planning-live'
Start-Process -FilePath $maven -ArgumentList @(
    "-Dgenb.build.directory=$backendBuild", 'spring-boot:run'
) -WorkingDirectory $backendDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'backend.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'backend.stderr.log') | Out-Null
Wait-Url "$backendUrl/actuator/health" 90

$env:PLANNING_REASONING_POSTGRES_DSN = "host=127.0.0.1 port=5432 dbname=genb_local user=$dbUser password=$dbPassword sslmode=disable"
$env:PLANNING_REASONING_AUTH_MODE = 'genb'
$env:PLANNING_REASONING_GENB_URL = $backendUrl
$env:PLANNING_REASONING_GENB_INTERNAL_TOKEN = $internalToken
$env:PYTHONPATH = Join-Path $planningDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'planning_reasoning.main:app', '--host', '127.0.0.1', '--port', '18712'
) -WorkingDirectory $planningDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'planning.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'planning.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18712/health/ready'

$env:SHORT_TERM_MEMORY_STORE = 'redis'
$env:SHORT_TERM_MEMORY_REDIS_HOST = '127.0.0.1'
$env:SHORT_TERM_MEMORY_REDIS_PORT = '6379'
$env:SHORT_TERM_MEMORY_REDIS_PASSWORD = $RedisPassword
$env:SHORT_TERM_MEMORY_AUTH_MODE = 'genb'
$env:SHORT_TERM_MEMORY_GENB_URL = $backendUrl
$env:SHORT_TERM_MEMORY_GENB_INTERNAL_TOKEN = $internalToken
$env:PYTHONPATH = Join-Path $memoryDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'short_term_memory.main:app', '--host', '127.0.0.1', '--port', '18705'
) -WorkingDirectory $memoryDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'short-memory.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'short-memory.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18705/health/ready'

$login = Invoke-RestMethod -Method Post -Uri "$backendUrl/v1/auth/login" -ContentType 'application/json' `
    -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)
$script:token = $login.data.token

$existingAgent = Invoke-RestMethod -Method Get -Uri "$backendUrl/v1/agents/$agentId" `
    -Headers @{ Authorization = "Bearer $script:token" }
if ($existingAgent.code -ne 200) {
    Invoke-GenB Post '/v1/agents' @{
        agentId = $agentId; name = '规划与推理核心组件测试智能体'
        nameEn = 'Planning and Reasoning Core Component Test Agent'
        description = '通过GenB绑定真实调用规划与推理引擎，测试需求澄清、Skill生成、校验和修订。'
        descriptionEn = 'Tests requirement clarification, Skill generation, validation, and revision through the GenB-bound Planning and Reasoning component.'
        version = 'v1.0.0'; category = '核心组件测试'; categoryEn = 'Core Component Testing'; securityLevel = 'L3'
        status = 'AUTHORIZED'; runtimeState = 'RUNNING'; businessAttribute = 'SYSTEM_AGENT'
        businessStatus = 'RUNNING'; owner = $Username; host = '127.0.0.1'; port = 18713
        workDirectory = $agentDir
        startCommand = 'python -m uvicorn control_system_test_agent.web:app --host 127.0.0.1 --port 18713'
    } | Out-Null
} else {
    $agent = $existingAgent.data
    $agent.name = '规划与推理核心组件测试智能体'
    $agent.nameEn = 'Planning and Reasoning Core Component Test Agent'
    $agent.description = '通过GenB绑定真实调用规划与推理引擎，测试需求澄清、Skill生成、校验和修订。'
    $agent.descriptionEn = 'Tests requirement clarification, Skill generation, validation, and revision through the GenB-bound Planning and Reasoning component.'
    $agent.category = '核心组件测试'; $agent.categoryEn = 'Core Component Testing'
    $agent.status = 'AUTHORIZED'; $agent.runtimeState = 'RUNNING'; $agent.businessStatus = 'RUNNING'
    $agent.host = '127.0.0.1'; $agent.port = 18713; $agent.workDirectory = $agentDir
    $agent.startCommand = 'python -m uvicorn control_system_test_agent.web:app --host 127.0.0.1 --port 18713'
    Invoke-GenB Put "/v1/agents/$agentId" $agent | Out-Null
}

$contracts = @(Invoke-GenB Get '/v1/core-components/PLANNING_REASONING/contracts')
$contract = $contracts | Where-Object { $_.contractVersion -eq '1.0.0' -and $_.status -eq 'PUBLISHED' } | Select-Object -First 1
if (-not $contract) {
    $openApi = Invoke-RestMethod -Uri 'http://127.0.0.1:18712/openapi.json'
    $draft = Invoke-GenB Post '/v1/core-components/PLANNING_REASONING/contracts' @{
        contractVersion = '1.0.0'; protocol = 'HTTP'; sourceType = 'DOCUMENT_PASTE'; sourceFormat = 'JSON'
        sourceName = 'planning-reasoning-openapi.json'; changeSummary = '规划与推理引擎一期正式接口'
        openApiDocument = $openApi; documentText = $null; manualOperations = $null
    }
    $contract = Invoke-GenB Post "/v1/core-components/PLANNING_REASONING/contracts/$($draft.id):publish"
}

$detail = Invoke-GenB Get '/v1/core-components/PLANNING_REASONING'
$implementation = @($detail.implementations) | Where-Object { $_.implementationCode -eq 'planning-reasoning-service-v1' } | Select-Object -First 1
if (-not $implementation) {
    $implementation = Invoke-GenB Post '/v1/core-components/PLANNING_REASONING/implementations' @{
        implementationCode = 'planning-reasoning-service-v1'; owner = 'Control System'
        runtimeType = 'HTTP'; interfaceVersion = '1.0.0'; baseUrl = 'http://127.0.0.1:18712'
        healthUrl = 'http://127.0.0.1:18712/health/ready'; invocationAdapter = 'PLANNING_REASONING_V1'
    }
}
if ($implementation.status -ne 'REGISTERED') {
    $implementation = Invoke-GenB Post "/v1/core-components/PLANNING_REASONING/implementations/$($implementation.id):enable"
}

$detail = Invoke-GenB Get '/v1/core-components/PLANNING_REASONING'
$config = @($detail.configVersions) | Where-Object {
    $_.implementationCode -eq 'planning-reasoning-service-v1' -and $_.profileCode -eq 'default' -and $_.status -eq 'PUBLISHED'
} | Select-Object -First 1
if (-not $config) {
    $draft = Invoke-GenB Post '/v1/core-components/PLANNING_REASONING/configs' @{
        implementationCode = 'planning-reasoning-service-v1'; profileCode = 'default'
        config = @{ authoring = 'TEMPLATE'; persistence = 'POSTGRESQL'; executesTools = $false }
        secretRefs = @(); changeSummary = '规划服务一期默认配置'
    }
    $config = Invoke-GenB Post "/v1/core-components/PLANNING_REASONING/configs/$($draft.id):publish"
}

$detail = Invoke-GenB Get '/v1/core-components/PLANNING_REASONING'
$binding = @($detail.bindings) | Where-Object { $_.agentId -eq $agentId } | Select-Object -First 1
if (-not $binding) {
    $binding = Invoke-GenB Post '/v1/core-components/PLANNING_REASONING/bindings' @{
        agentId = $agentId; implementationCode = 'planning-reasoning-service-v1'; configVersionId = $config.id
    }
} elseif ($binding.status -ne 'ENABLED') {
    $binding = Invoke-GenB Post "/v1/core-components/PLANNING_REASONING/bindings/$($binding.id):enable"
}

$credentialPath = Join-Path $secretDir "$agentId.credential.dpapi"
if ((Test-Path $credentialPath) -and -not $RotateAgentCredential) {
    $credential = Read-ProtectedSecret $credentialPath
} else {
    $issued = Invoke-GenB Post '/v1/service-credentials' @{
        agentId = $agentId; name = 'Planning test agent runtime'
        scopes = @('component:planning-reasoning:invoke'); expiresAt = $null
    }
    $credential = $issued.credentialSecret
    Save-ProtectedSecret $credentialPath $credential
}

$env:AGENT_ID = $agentId
$env:GENB_BASE_URL = $backendUrl
$env:SERVICE_CREDENTIAL = $credential
$env:PYTHONPATH = Join-Path $agentDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system_test_agent.web:app', '--host', '127.0.0.1', '--port', '18713'
) -WorkingDirectory $agentDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'agent.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'agent.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18713/health/live'

Write-Output "Planning integration ready: backend=8581, planning=18712, agent=18713, implementation=$($implementation.id), config=$($config.id), binding=$($binding.id)"
