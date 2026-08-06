param(
    [Parameter(Mandatory = $true)][string]$Password,
    [Parameter(Mandatory = $true)][string]$RedisPassword,
    [string]$Username = 'admin',
    [switch]$RotateAgentCredential
)

$ErrorActionPreference = 'Stop'
$root = 'D:\code\opencode\genb'
$backendDir = Join-Path $root 'gen-b\gen-b-backend'
$runtimeDir = Join-Path $root 'runtime-system-service'
$planningDir = Join-Path $root 'planning-reasoning-service'
$memoryDir = Join-Path $root 'short-term-memory-service'
$controlDir = Join-Path $root 'control-system-service'
$agentDir = Join-Path $root 'control-system-test-agent'
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
$maven = 'D:\environment\maven\apache-maven-3.6.3\bin\mvn.cmd'
$secretDir = Join-Path $root '.local-secrets'
$logDir = Join-Path $root '.logs\customer-core-agent-local'
$backendUrl = 'http://127.0.0.1:8581/api'
$agentId = 'core-component-demo-agent'

function Read-ProtectedSecret([string]$Path) {
    $encrypted = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secure = $encrypted | ConvertTo-SecureString
    return [Net.NetworkCredential]::new('', $secure).Password
}

function Save-ProtectedSecret([string]$Path, [string]$Value) {
    ConvertTo-SecureString $Value -AsPlainText -Force |
        ConvertFrom-SecureString |
        Set-Content -LiteralPath $Path -Encoding ASCII
}

function Stop-ExpectedPort([int]$Port, [string]$Expected) {
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
        Headers = @{ Authorization = "Bearer $script:userToken" }
        ContentType = 'application/json; charset=utf-8'
    }
    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 100
        $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
    }
    try {
        $response = Invoke-RestMethod @parameters
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        throw "GenB request failed: $Method $Path (HTTP $status)"
    }
    if ($response.code -ne 200) { throw "GenB request failed: $Path" }
    return $response.data
}

function Get-OrCreateBinding([string]$ComponentCode, [string]$ImplementationCode, [long]$ConfigVersionId) {
    $detail = Invoke-GenB Get "/v1/core-components/$ComponentCode"
    $binding = @($detail.bindings) | Where-Object { $_.agentId -eq $agentId } | Select-Object -First 1
    if (-not $binding) {
        return Invoke-GenB Post "/v1/core-components/$ComponentCode/bindings" @{
            agentId = $agentId
            implementationCode = $ImplementationCode
            configVersionId = $ConfigVersionId
        }
    }
    if ($binding.implementationCode -ne $ImplementationCode -or $binding.configVersionId -ne $ConfigVersionId) {
        if ($binding.status -eq 'ENABLED') {
            Invoke-GenB Post "/v1/core-components/$ComponentCode/bindings/$($binding.id):disable" | Out-Null
        }
        return Invoke-GenB Post "/v1/core-components/$ComponentCode/bindings" @{
            agentId = $agentId
            implementationCode = $ImplementationCode
            configVersionId = $ConfigVersionId
        }
    }
    if ($binding.status -ne 'ENABLED') {
        return Invoke-GenB Post "/v1/core-components/$ComponentCode/bindings/$($binding.id):enable"
    }
    return $binding
}

New-Item -ItemType Directory -Path $secretDir, $logDir -Force | Out-Null
$internalSecretPath = Join-Path $secretDir 'genb-component-internal-token.dpapi'
if (-not (Test-Path -LiteralPath $internalSecretPath)) {
    throw 'GenB component internal token has not been initialized'
}
$internalToken = Read-ProtectedSecret $internalSecretPath

$application = Get-Content -LiteralPath (Join-Path $backendDir 'src\main\resources\application.yml') -Raw
$userMatch = [regex]::Match($application, 'GENB_DB_USERNAME:([^}]+)')
$passwordMatch = [regex]::Match($application, 'GENB_DB_PASSWORD:([^}]+)')
$dbUser = if ($env:GENB_DB_USERNAME) { $env:GENB_DB_USERNAME } elseif ($userMatch.Success) { $userMatch.Groups[1].Value.Trim() } else { [regex]::Match($application, 'username:\s+([^\r\n]+)').Groups[1].Value.Trim() }
$dbPassword = if ($env:GENB_DB_PASSWORD) { $env:GENB_DB_PASSWORD } elseif ($passwordMatch.Success) { $passwordMatch.Groups[1].Value.Trim() } else { [regex]::Match($application, 'password:\s+([^\r\n]+)').Groups[1].Value.Trim() }
$env:GENB_DB_URL = 'jdbc:postgresql://127.0.0.1:5432/genb_local?currentSchema=bank_agent_db&sslmode=disable'
$env:GENB_DB_USERNAME = $dbUser
$env:GENB_DB_PASSWORD = $dbPassword
$env:GENB_REDIS_HOST = '127.0.0.1'
$env:GENB_REDIS_PORT = '6379'
$env:GENB_REDIS_PASSWORD = $RedisPassword

Stop-ExpectedPort 8581 'GenBConsoleApplication'
$env:CONTROL_SYSTEM_INTERNAL_TOKEN = $internalToken
$env:COMPONENT_ACTOR_KEY_ID = 'genb-local-customer-agent'
$env:COMPONENT_ACTOR_PRIVATE_KEY_PATH = Join-Path $backendDir 'local-iteration11-actor.pem'
$env:GENB_TENANT_ID = 'genb-local'
$backendBuild = Join-Path $root '.tmp\genb-backend-customer-agent-live'
Start-Process -FilePath $maven -ArgumentList @(
    "-Dgenb.build.directory=$backendBuild", 'spring-boot:run'
) -WorkingDirectory $backendDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'backend.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'backend.stderr.log') | Out-Null
Wait-Url "$backendUrl/actuator/health" 90

Stop-ExpectedPort 18705 'short_term_memory.main:app'
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
$script:userToken = $login.data.token

try {
    $existingAgent = Invoke-RestMethod -Method Get -Uri "$backendUrl/v1/agents/$agentId" `
        -Headers @{ Authorization = "Bearer $script:userToken" }
} catch {
    $existingAgent = $null
}
if (-not $existingAgent -or $existingAgent.code -ne 200) {
    Invoke-GenB Post '/v1/agents' @{
        agentId = $agentId
        name = '核心组件智能体'
        nameEn = 'Core Component Agent'
        description = '面向客户的真实智能体，通过自然语言验证短期记忆、规划与推理及模型推理能力。'
        descriptionEn = 'A customer-facing agent that validates short-term memory, planning and reasoning, and model inference through natural-language conversation.'
        version = 'v1.0.0'
        category = '核心组件体验'
        categoryEn = 'Core Component Experience'
        securityLevel = 'L3'
        status = 'AUTHORIZED'
        runtimeState = 'RUNNING'
        businessAttribute = 'SYSTEM_AGENT'
        businessStatus = 'RUNNING'
        owner = $Username
        host = '127.0.0.1'
        port = 18714
        accessUrl = 'http://localhost:18714/'
        callbackUrl = 'http://localhost:18714/auth/callback'
        workDirectory = $agentDir
        startCommand = 'python -m uvicorn control_system_test_agent.web:app --host 127.0.0.1 --port 18714'
    } | Out-Null
} else {
    $agent = $existingAgent.data
    $agent.name = '核心组件智能体'; $agent.nameEn = 'Core Component Agent'
    $agent.description = '面向客户的真实智能体，通过自然语言验证短期记忆、规划与推理及模型推理能力。'
    $agent.descriptionEn = 'A customer-facing agent that validates short-term memory, planning and reasoning, and model inference through natural-language conversation.'
    $agent.category = '核心组件体验'; $agent.categoryEn = 'Core Component Experience'
    $agent.status = 'AUTHORIZED'; $agent.runtimeState = 'RUNNING'; $agent.businessStatus = 'RUNNING'
    $agent.host = '127.0.0.1'; $agent.port = 18714; $agent.accessUrl = 'http://localhost:18714/'; $agent.workDirectory = $agentDir
    $agent.callbackUrl = 'http://localhost:18714/auth/callback'
    $agent.startCommand = 'python -m uvicorn control_system_test_agent.web:app --host 127.0.0.1 --port 18714'
    Invoke-GenB Put "/v1/agents/$agentId" $agent | Out-Null
}

$runtimeDetail = Invoke-GenB Get '/v1/core-components/INFERENCE_ENGINE'
$runtimeImplementation = @($runtimeDetail.implementations) | Where-Object {
    $_.implementationCode -eq 'runtime-inference-deepseek-v1'
} | Select-Object -First 1
if (-not $runtimeImplementation) {
    $runtimeImplementation = Invoke-GenB Post '/v1/core-components/INFERENCE_ENGINE/implementations' @{
        implementationCode = 'runtime-inference-deepseek-v1'
        owner = 'Runtime System'
        runtimeType = 'HTTP'
        interfaceVersion = '1.0.0'
        baseUrl = 'http://127.0.0.1:18704'
        healthUrl = 'http://127.0.0.1:18704/health/ready'
        invocationAdapter = 'RUNTIME_INFERENCE_V1'
    }
}
if ($runtimeImplementation.status -ne 'REGISTERED') {
    $runtimeImplementation = Invoke-GenB Post "/v1/core-components/INFERENCE_ENGINE/implementations/$($runtimeImplementation.id):enable"
}
$runtimeDetail = Invoke-GenB Get '/v1/core-components/INFERENCE_ENGINE'
$runtimeConfig = @($runtimeDetail.configVersions) | Where-Object {
    $_.implementationCode -eq 'runtime-inference-deepseek-v1' -and $_.profileCode -eq 'customer-agent' -and $_.status -eq 'PUBLISHED'
} | Select-Object -First 1
if (-not $runtimeConfig) {
    $draft = Invoke-GenB Post '/v1/core-components/INFERENCE_ENGINE/configs' @{
        implementationCode = 'runtime-inference-deepseek-v1'
        profileCode = 'customer-agent'
        config = @{
            provider = 'DIRECT_OPENAI_COMPATIBLE'
            modelAliases = @(
                'agent-chat-default',
                'planning-analysis-default',
                'planning-authoring-default',
                'memory-extraction-default'
            )
            providerConfiguration = 'RUNTIME_PROCESS_ENVIRONMENT'
        }
        secretRefs = @()
        changeSummary = '客户核心组件智能体真实模型配置'
    }
    $runtimeConfig = Invoke-GenB Post "/v1/core-components/INFERENCE_ENGINE/configs/$($draft.id):publish"
}

$memoryDetail = Invoke-GenB Get '/v1/core-components/SHORT_TERM_MEMORY'
$memoryImplementation = @($memoryDetail.implementations) | Where-Object {
    $_.implementationCode -eq 'standalone-short-term-memory-v1' -and $_.status -eq 'REGISTERED'
} | Select-Object -First 1
if (-not $memoryImplementation) {
    throw 'Standalone short-term memory implementation is not registered and enabled'
}
$memoryConfig = @($memoryDetail.configVersions) | Where-Object {
    $_.implementationCode -eq $memoryImplementation.implementationCode -and $_.status -eq 'PUBLISHED'
} | Select-Object -First 1
$planningDetail = Invoke-GenB Get '/v1/core-components/PLANNING_REASONING'
$planningImplementation = @($planningDetail.implementations) | Where-Object {
    $_.implementationCode -eq 'planning-reasoning-service-v1' -and $_.status -eq 'REGISTERED'
} | Select-Object -First 1
if (-not $planningImplementation) {
    throw 'Planning reasoning implementation is not registered and enabled'
}
$planningConfig = @($planningDetail.configVersions) | Where-Object {
    $_.implementationCode -eq $planningImplementation.implementationCode -and $_.status -eq 'PUBLISHED'
} | Select-Object -First 1
if (-not $memoryImplementation -or -not $memoryConfig -or -not $planningImplementation -or -not $planningConfig) {
    throw 'Short-term memory or planning implementation/configuration is not ready'
}
$longTermDetail = Invoke-GenB Get '/v1/core-components/LONG_TERM_MEMORY'
$longTermImplementation = @($longTermDetail.implementations) | Where-Object {
    $_.implementationCode -eq 'long-term-memory-service-v1'
} | Select-Object -First 1
if (-not $longTermImplementation) {
    $longTermImplementation = Invoke-GenB Post '/v1/core-components/LONG_TERM_MEMORY/implementations' @{
        implementationCode = 'long-term-memory-service-v1'
        owner = 'Long-term Memory Service'
        runtimeType = 'HTTP'
        interfaceVersion = '1.0.0'
        baseUrl = 'http://127.0.0.1:18702'
        healthUrl = 'http://127.0.0.1:18702/health/ready'
        invocationAdapter = 'LONG_TERM_MEMORY_V1'
    }
}
if ($longTermImplementation.status -ne 'REGISTERED') {
    $longTermImplementation = Invoke-GenB Post "/v1/core-components/LONG_TERM_MEMORY/implementations/$($longTermImplementation.id):enable"
}
$longTermDetail = Invoke-GenB Get '/v1/core-components/LONG_TERM_MEMORY'
$longTermConfig = @($longTermDetail.configVersions) | Where-Object {
    $_.implementationCode -eq $longTermImplementation.implementationCode `
        -and $_.profileCode -eq 'conversation-memory' `
        -and $_.status -eq 'PUBLISHED' `
        -and $_.config.modelAlias -eq 'memory-extraction-default'
} | Select-Object -First 1
if (-not $longTermConfig) {
    $draft = Invoke-GenB Post '/v1/core-components/LONG_TERM_MEMORY/configs' @{
        implementationCode = $longTermImplementation.implementationCode
        profileCode = 'conversation-memory'
        config = @{
            enabledTypes = @('USER_PREFERENCE', 'STABLE_FACT', 'USER_CONSTRAINT')
            autoExtractionEnabled = $true
            confidenceThreshold = 0.8
            retentionDays = 180
            topK = 5
            maxTopK = 20
            modelAlias = 'memory-extraction-default'
            maxAttempts = 3
        }
        secretRefs = @()
        changeSummary = '18714长期对话记忆独立测试配置'
    }
    $longTermConfig = Invoke-GenB Post "/v1/core-components/LONG_TERM_MEMORY/configs/$($draft.id):publish"
}

$memoryBinding = Get-OrCreateBinding 'SHORT_TERM_MEMORY' $memoryImplementation.implementationCode $memoryConfig.id
$longTermBinding = Get-OrCreateBinding 'LONG_TERM_MEMORY' $longTermImplementation.implementationCode $longTermConfig.id
$planningBinding = Get-OrCreateBinding 'PLANNING_REASONING' $planningImplementation.implementationCode $planningConfig.id
$runtimeBinding = Get-OrCreateBinding 'INFERENCE_ENGINE' $runtimeImplementation.implementationCode $runtimeConfig.id

$longTermDetail = Invoke-GenB Get '/v1/core-components/LONG_TERM_MEMORY'
$legacyLongTermImplementation = @($longTermDetail.implementations) | Where-Object {
    $_.implementationCode -eq 'control-long-term-memory-iteration13' -and $_.status -ne 'DISABLED'
} | Select-Object -First 1
if ($legacyLongTermImplementation) {
    Invoke-GenB Post "/v1/core-components/LONG_TERM_MEMORY/implementations/$($legacyLongTermImplementation.id):disable" | Out-Null
}

$credentialPath = Join-Path $secretDir "$agentId.credential.dpapi"
if ((Test-Path -LiteralPath $credentialPath) -and -not $RotateAgentCredential) {
    $credential = Read-ProtectedSecret $credentialPath
} else {
    $issued = Invoke-GenB Post '/v1/service-credentials' @{
        agentId = $agentId
        name = 'Customer core component agent runtime'
        scopes = @(
            'component:short-term-memory:read',
            'component:short-term-memory:write',
            'component:short-term-memory:delete',
            'component:long-term-memory:read',
            'component:long-term-memory:write',
            'component:long-term-memory:delete',
            'component:planning-reasoning:invoke',
            'component:inference-engine:infer'
        )
        expiresAt = $null
    }
    $credential = $issued.credentialSecret
    Save-ProtectedSecret $credentialPath $credential
}

Stop-ExpectedPort 18704 'runtime_system.main:app'
Stop-ExpectedPort 18702 'long_term_memory.main:app'
Stop-ExpectedPort 18701 'control_system.main:create_application'
Stop-ExpectedPort 18712 'planning_reasoning.main:app'
Stop-ExpectedPort 18714 'control_system_test_agent.web:app'

$env:APP_ENV = 'local'
$env:RUNTIME_STATIC_TOKEN = $credential
$env:RUNTIME_LOCAL_ENV_FILE = Join-Path $root 'C01智能审单专家智能体\.env'
$env:MODEL_ROUTING_CONFIG = Join-Path $runtimeDir 'config\model-routing.deepseek.json'
$env:PYTHONPATH = Join-Path $runtimeDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'runtime_system.main:app', '--host', '127.0.0.1', '--port', '18704'
) -WorkingDirectory $runtimeDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'runtime.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'runtime.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18704/health/ready'

& (Join-Path $root 'scripts\start_long_term_memory_service_local.ps1') | Out-Null
Wait-Url 'http://127.0.0.1:18702/health/ready'

$env:APP_ENV = 'local'
$env:CONTROL_SYSTEM_IDENTITY_ADAPTER = 'genb'
$env:GENB_BASE_URL = 'http://127.0.0.1:8581'
$env:CONTROL_SYSTEM_INTERNAL_TOKEN = $internalToken
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = '6379'
$env:REDIS_PASSWORD = $RedisPassword
$env:REDIS_KEY_PEPPER = $internalToken
$env:RUNTIME_INFERENCE_BASE_URL = 'http://127.0.0.1:18704'
$env:CONTROL_SYSTEM_RUNTIME_TOKEN = $credential
$env:PYTHONPATH = Join-Path $controlDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system.main:create_application', '--factory', '--host', '127.0.0.1', '--port', '18701'
) -WorkingDirectory $controlDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'control.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'control.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18701/health/ready'

$env:PLANNING_REASONING_POSTGRES_DSN = "host=127.0.0.1 port=5432 dbname=genb_local user=$dbUser password=$dbPassword sslmode=disable options='-c search_path=bank_agent_db'"
$env:PLANNING_REASONING_AUTH_MODE = 'genb'
$env:PLANNING_REASONING_GENB_URL = $backendUrl
$env:PLANNING_REASONING_GENB_INTERNAL_TOKEN = $internalToken
$env:PLANNING_REASONING_INFERENCE_URL = 'http://127.0.0.1:18704'
$env:PLANNING_REASONING_MODEL_ALIAS = 'planning-authoring-default'
$env:PLANNING_REASONING_ANALYSIS_MODEL_ALIAS = 'planning-analysis-default'
$env:PYTHONPATH = Join-Path $planningDir 'src'
& $python (Join-Path $planningDir 'scripts\apply_migrations.py')
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'planning_reasoning.main:app', '--host', '127.0.0.1', '--port', '18712'
) -WorkingDirectory $planningDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'planning.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'planning.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18712/health/ready'

$env:AGENT_ID = $agentId
$env:GENB_BASE_URL = $backendUrl
$env:SERVICE_CREDENTIAL = $credential
$env:HTTP_TIMEOUT_SECONDS = '90'
$env:AGENT_REDIS_HOST = '127.0.0.1'
$env:AGENT_REDIS_PORT = '6379'
$env:AGENT_REDIS_PASSWORD = $RedisPassword
$env:CONTROL_SYSTEM_BASE_URL = 'http://127.0.0.1:18701'
$env:AGENT_CALLBACK_URL = 'http://localhost:18714/auth/callback'
$env:PORTAL_AGENT_SSO_URL = 'http://localhost:9100/agent-sso'
$env:PYTHONPATH = Join-Path $agentDir 'src'
Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'control_system_test_agent.web:app', '--host', '127.0.0.1', '--port', '18714'
) -WorkingDirectory $agentDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'agent.stdout.log') `
  -RedirectStandardError (Join-Path $logDir 'agent.stderr.log') | Out-Null
Wait-Url 'http://127.0.0.1:18714/health/live'

Write-Output "Customer core agent ready: direct=http://127.0.0.1:18714/, bindings=$($memoryBinding.id),$($longTermBinding.id),$($planningBinding.id),$($runtimeBinding.id)"
