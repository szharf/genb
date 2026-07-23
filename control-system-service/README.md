# GenB Control System Service

Control System 执行面服务。Iteration 9—12完成Short-term Memory、GenB身份、动态配置、摘要和可观测性；Iteration 13完成结构化Long-term Memory一期。不存在额外的 Memory Runtime Service 层，也不依赖旧 `bank-agent-runtime`/SDK。

## 已实现

- `POST /api/v1/control-system/short-term-memory/turns:commit`
- `POST /api/v1/control-system/short-term-memory/context:prepare`
- `DELETE /api/v1/control-system/short-term-memory/sessions/{sessionId}`
- `POST /api/v1/control-system/long-term-memory/extractions`
- `GET /api/v1/control-system/long-term-memory/extractions/{extractionId}`
- `POST /api/v1/control-system/long-term-memory/search`
- `POST /api/v1/control-system/long-term-memory/memories/{memoryId}:delete`
- 服务凭证 + RS256 Actor Token 双凭证验证。
- GenB HTTP内省Adapter与按`kid`选择公钥的JWKS Adapter；依赖异常fail-closed。
- tenant/user/agent/session 四维隔离。
- 幂等重放、内容冲突、最近消息预算、密码/Token持久化前脱敏。
- In-memory Adapter 与 Redis Adapter；Redis使用Lua原子提交、TTL和HMAC键。
- GenB已发布配置按Actor Token中的`configVersionId`读取和缓存；非法、草稿或不可用配置fail-closed。
- 摘要通过Control拥有的`SummaryGenerator` Port调用我方Runtime Inference Interface；Fake只用于测试，失败保留最近窗口并标记降级。
- Redis摘要独立存储，使用`throughTurnId`乐观检查阻止旧任务覆盖新摘要。
- `/health/live`、`/health/ready`、`/version`、`/metrics`和版本化OpenAPI；日志和指标不记录正文或凭证。

## 身份模式

- `CONTROL_SYSTEM_IDENTITY_ADAPTER=local`：只允许`APP_ENV=local|test`，使用本地凭证文件和RSA公钥。
- `CONTROL_SYSTEM_IDENTITY_ADAPTER=genb`：通过`GENB_BASE_URL`调用GenB内省和JWKS Interface；生产环境强制HTTPS。
- 两种模式都强制服务凭证与Actor Token的agent一致，并使用`component:short-term-memory:<action>` scope。
- 当前不缓存内省结果或JWKS，GenB不可用时请求立即fail-closed。组件配置只按不可变版本ID短缓存。

## Long-term Memory

- 一期只允许`USER_PREFERENCE`、`STABLE_FACT`、`USER_CONSTRAINT`，不是完整RAG知识库。
- PostgreSQL Adapter按tenant/user/agent完整scope读写；提取任务、事件、记忆和删除审计共4张表，实际建表无物理外键。
- Worker使用持久化PENDING任务、60秒租约、过期恢复、指数退避和有限重试；非法结构化输出转为`NO_WRITE`，临时Inference故障最终进入`DEAD`。
- 输入持久化前脱敏，模型候选写入前再次做类型、置信度、长度和敏感内容过滤。
- `CONTROL_SYSTEM_POSTGRES_DSN`配置后启用PostgreSQL和后台Worker；production环境必填。
- `GENB_BASE_URL`必须是主机根地址（例如`http://127.0.0.1:8581`），不要附加`/api`，内部Adapter路径已经包含该前缀。

发布配置示例：

```json
{
  "enabledTypes": ["USER_PREFERENCE", "STABLE_FACT", "USER_CONSTRAINT"],
  "autoExtractionEnabled": true,
  "confidenceThreshold": 0.8,
  "retentionDays": 180,
  "topK": 5,
  "maxTopK": 20,
  "modelAlias": "memory-extraction-default",
  "maxAttempts": 3
}
```

## Short-term Memory发布配置

```json
{
  "schemaVersion": "1.0",
  "ttlSeconds": 86400,
  "maxTurns": 50,
  "maxContextTokens": 16000,
  "summaryEnabled": true,
  "summaryTriggerTurns": 20,
  "summaryModelAlias": "session-summary-default"
}
```

`ttlSeconds`、`maxTurns`、`maxContextTokens`为必填并有严格范围；摘要字段可选，缺省关闭摘要。配置必须先在GenB发布并绑定，Control不会接受请求正文覆盖配置。

## 测试

复用当前工作区已有Python 3.12/FastAPI环境（项目契约支持Python 3.11+），不需要临时下载依赖。

```powershell
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
& $python -m pytest -q
```

真实Redis集成测试只从环境取密码：

```powershell
$env:CONTROL_SYSTEM_TEST_REDIS_PASSWORD = '<local test password>'
& $python -m pytest tests/integration/test_redis_session_store.py -q
```

测试使用Redis DB 15和唯一前缀，结束后只精确删除该前缀数据。

## 本地启动

1. 复制 `.env.example` 到Git忽略的本地环境配置。
2. 准备测试RSA公钥文件和Git忽略的本地凭证JSON：

```json
[
  {
    "token": "<local-service-token>",
    "credentialId": "credential-test-a",
    "agentId": "memory-test-a",
    "scopes": [
      "component:short-term-memory:read",
      "component:short-term-memory:write",
      "component:short-term-memory:delete"
    ]
  }
]
```

3. 注入环境变量后启动：

```powershell
$env:PYTHONPATH = 'src'
& $python -m uvicorn control_system.main:create_application --factory --host 127.0.0.1 --port 8701
```

连接本地GenB时无需本地凭证JSON或公钥文件，改用：

```powershell
$env:APP_ENV = 'local'
$env:CONTROL_SYSTEM_IDENTITY_ADAPTER = 'genb'
$env:GENB_BASE_URL = 'http://127.0.0.1:8581'
$env:CONTROL_SYSTEM_INTERNAL_TOKEN = '<same value configured in GenB>'
$env:RUNTIME_INFERENCE_BASE_URL = 'http://127.0.0.1:8704'
$env:CONTROL_SYSTEM_RUNTIME_TOKEN = '<runtime service credential>'
```

生产环境强制GenB与Runtime Inference使用HTTPS，并要求摘要Adapter配置完整。本地缺Runtime配置时不会伪造摘要，`/health/ready`会在显式启用该Adapter的运行模式中报告`runtime-inference`降级。

GenB需要由环境提供`GENB_TENANT_ID`、`COMPONENT_ACTOR_KEY_ID`、`COMPONENT_ACTOR_PRIVATE_KEY_PATH`和`CONTROL_SYSTEM_INTERNAL_TOKEN`。私钥使用PKCS#8 PEM且不得小于2048 bit；JWKS仅发布相应公钥。不要把这些值或私钥提交到Git。

## OpenAPI

`openapi/control-system-v1.json` 是已提交契约，必须与FastAPI导出一致：

```powershell
$env:PYTHONPATH = 'src'
& $python scripts/export_openapi.py
& $python -m pytest tests/contract/test_openapi_contract.py -q
```
