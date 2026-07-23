# Runtime System Service

GenB核心组件平台的Runtime System一期实现。当前Iteration 1提供可运行的Fake Inference纵向切片，不访问外部模型、不包含真实凭证，也不依赖旧`bank-agent-runtime`。

## 当前Interface

| Method | Path | Scope |
|---|---|---|
| POST | `/api/v1/runtime-system/inference` | `component:inference-engine:infer` |
| POST | `/api/v1/runtime-system/inference:stream` | `component:inference-engine:infer` |
| POST | `/api/v1/runtime-system/embeddings` | `component:inference-engine:embed` |
| GET | `/api/v1/runtime-system/models` | `component:inference-engine:models:read` |
| GET | `/health/live` | 无 |
| GET | `/health/ready` | 无 |
| GET | `/internal/health/models` | `component:inference-engine:health:read` |

静态契约见`openapi/runtime-inference-v1.json`。FastAPI运行时契约见`/openapi.json`。

## 运行要求

- Python `>=3.11`
- FastAPI、Pydantic、HTTPX、Uvicorn
- 测试使用pytest

本轮没有安装依赖；验证复用了工作区已有Python环境。正式开发环境应在D盘建立本服务自己的虚拟环境并按`pyproject.toml`锁定依赖。

## 本地启动

PowerShell：

```powershell
$env:APP_ENV='local'
$env:RUNTIME_STATIC_TOKEN='<local-only-token>'
$env:PYTHONPATH='D:\code\opencode\genb\runtime-system-service\src'
& '<python-path>' -m uvicorn runtime_system.main:app --host 127.0.0.1 --port 8704
```

`RUNTIME_STATIC_TOKEN`只用于本地Iteration 1。`APP_ENV=production`时不会加载它，并且Fake Provider会使`/health/ready`返回503。

## 测试

```powershell
& '<python-path>' -m pytest -q
```

测试通过公开HTTP Interface覆盖：认证、scope、普通Inference、结构化输出、非法模型结果、Embedding、维度错误、模型能力、live/ready、生产禁止Fake和SSE生命周期。

## 结构化输出限制

当前不安装额外JSON Schema库，使用fail-closed受限子集：

- `type`
- `required`
- `properties`
- `additionalProperties`
- `items`
- `enum`
- `minLength/maxLength`
- `minItems/maxItems`

遇到未知关键字会拒绝，而不是忽略。M2依赖评审后可以用完整Draft 2020-12 Adapter替换，外部Inference Interface不变。

## 安全边界

- 默认没有可用静态Token。
- 生产环境禁止Static Token和Fake Provider ready。
- 不记录或返回Provider密钥。
- Control System和智能体只使用GenB身份调用该Interface。
- Direct Provider、JWT/mTLS、配额、限流和Secrets属于后续迭代。
