# GenB Control System Service

Control System 执行面服务。Iteration 9 实现 Short-term Memory 的第一条真实纵向切片，不存在额外的 Memory Runtime Service 层，也不依赖旧 `bank-agent-runtime`/SDK。

## 已实现

- `POST /api/v1/control-system/short-term-memory/turns:commit`
- `POST /api/v1/control-system/short-term-memory/context:prepare`
- `DELETE /api/v1/control-system/short-term-memory/sessions/{sessionId}`
- 服务凭证 + RS256 Actor Token 双凭证验证。
- tenant/user/agent/session 四维隔离。
- 幂等重放、内容冲突、最近消息预算、密码/Token持久化前脱敏。
- In-memory Adapter 与 Redis Adapter；Redis使用Lua原子提交、TTL和HMAC键。
- `/health/live`、`/health/ready`、`/version` 和版本化OpenAPI。

## 当前边界

- 当前启动工厂只允许 `APP_ENV=local|test`，并使用本地凭证文件Adapter。
- `production` 会直接拒绝启动；必须先完成GenB服务凭证内省Adapter、非对称签名/JWKS轮换和安全评审。
- 本轮不包含Long-term Memory、摘要、模型调用、测试智能体或管理端测试台。

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
    "scopes": ["short-term:read", "short-term:write", "short-term:delete"]
  }
]
```

3. 注入环境变量后启动：

```powershell
$env:PYTHONPATH = 'src'
& $python -m uvicorn control_system.main:create_application --factory --host 127.0.0.1 --port 8701
```

## OpenAPI

`openapi/control-system-v1.json` 是已提交契约，必须与FastAPI导出一致：

```powershell
$env:PYTHONPATH = 'src'
& $python scripts/export_openapi.py
& $python -m pytest tests/contract/test_openapi_contract.py -q
```
