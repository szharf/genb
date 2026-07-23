# GenB Control System Service

Control System 执行面服务。Iteration 9 实现 Short-term Memory 的第一条真实纵向切片；Iteration 10 接入GenB服务凭证内省和Actor Token JWKS。不存在额外的 Memory Runtime Service 层，也不依赖旧 `bank-agent-runtime`/SDK。

## 已实现

- `POST /api/v1/control-system/short-term-memory/turns:commit`
- `POST /api/v1/control-system/short-term-memory/context:prepare`
- `DELETE /api/v1/control-system/short-term-memory/sessions/{sessionId}`
- 服务凭证 + RS256 Actor Token 双凭证验证。
- GenB HTTP内省Adapter与按`kid`选择公钥的JWKS Adapter；依赖异常fail-closed。
- tenant/user/agent/session 四维隔离。
- 幂等重放、内容冲突、最近消息预算、密码/Token持久化前脱敏。
- In-memory Adapter 与 Redis Adapter；Redis使用Lua原子提交、TTL和HMAC键。
- `/health/live`、`/health/ready`、`/version` 和版本化OpenAPI。

## 身份模式

- `CONTROL_SYSTEM_IDENTITY_ADAPTER=local`：只允许`APP_ENV=local|test`，使用本地凭证文件和RSA公钥。
- `CONTROL_SYSTEM_IDENTITY_ADAPTER=genb`：通过`GENB_BASE_URL`调用GenB内省和JWKS Interface；生产环境强制HTTPS。
- 两种模式都强制服务凭证与Actor Token的agent一致，并使用`component:short-term-memory:<action>` scope。
- 当前不缓存内省结果或JWKS，GenB不可用时请求立即fail-closed。密钥轮换缓存、Long-term Memory、测试智能体和管理端测试台仍属后续范围。

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
```

GenB需要由环境提供`GENB_TENANT_ID`、`COMPONENT_ACTOR_KEY_ID`、`COMPONENT_ACTOR_PRIVATE_KEY_PATH`和`CONTROL_SYSTEM_INTERNAL_TOKEN`。私钥使用PKCS#8 PEM且不得小于2048 bit；JWKS仅发布相应公钥。不要把这些值或私钥提交到Git。

## OpenAPI

`openapi/control-system-v1.json` 是已提交契约，必须与FastAPI导出一致：

```powershell
$env:PYTHONPATH = 'src'
& $python scripts/export_openapi.py
& $python -m pytest tests/contract/test_openapi_contract.py -q
```
