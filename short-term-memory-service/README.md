# GenB 短期记忆组件服务

短期记忆是一项独立的逻辑组件服务，提供多个 HTTP 接口；它可以与规划与推理等相关组件服务放在同一个 Control System 项目中部署，但接口、数据边界和生命周期保持独立。

本目录目前是可独立运行、可独立验收的参考实现，尚未接入 GenB 智能体调用链。GenB 本轮只登记它的接口契约，不登记真实实现地址，不创建智能体绑定。

## 能力范围

- 以 `tenantId + agentId + userId + taskId` 隔离数据。
- 保存任务工作台：临时指令、进度、待补材料、工具结果和恢复检查点。
- 提交一轮对话并通过 `Idempotency-Key` 防止重复写入。
- 在新 `sessionId` 中按 `taskId` 恢复最近消息及工作台。
- 支持 60 秒到 30 天的可配置 TTL。
- 密码、Token、验证码等值在写入前脱敏。
- 默认内存存储，生产方式支持 Redis；Redis 以单任务 JSON 文档原子更新。

## 本地启动

```powershell
Set-Location D:\code\opencode\genb\short-term-memory-service
$env:SHORT_TERM_MEMORY_STORE='in_memory'
& 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe' -m uvicorn short_term_memory.main:app --app-dir src --host 127.0.0.1 --port 18705
```

启动后访问：

- Swagger：`http://127.0.0.1:18705/docs`
- OpenAPI：`http://127.0.0.1:18705/openapi.json`
- 就绪检查：`http://127.0.0.1:18705/health/ready`

Redis 模式使用 `.env.example` 中列出的环境变量。密码只通过运行环境注入，不写入代码、接口契约或 GenB 普通配置。

## 接口清单

| operationId | 方法与路径 | 作用 |
|---|---|---|
| `saveTaskWorkbench` | `PUT /api/v1/short-term-memory/tasks/{taskId}` | 新建或覆盖任务工作台并设置 TTL |
| `getTaskWorkbench` | `GET /api/v1/short-term-memory/tasks/{taskId}` | 查询任务工作台 |
| `deleteTaskWorkbench` | `DELETE /api/v1/short-term-memory/tasks/{taskId}` | 删除任务及上下文 |
| `commitShortTermTurn` | `POST /api/v1/short-term-memory/turns:commit` | 幂等提交一轮对话 |
| `prepareShortTermContext` | `POST /api/v1/short-term-memory/context:prepare` | 为新的会话准备任务上下文 |

每个业务接口都必须携带 `X-Tenant-Id`、`X-Agent-Id` 和 `X-User-Id`。提交对话还必须携带 `Idempotency-Key`。这些身份头在正式接入时只能由已完成服务凭证、智能体身份与绑定校验的 GenB 运行入口注入，不能信任公网调用者自行填写。

## 测试

```powershell
& 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe' -m pytest -q
```

真实 Redis 测试仅在设置 `SHORT_TERM_MEMORY_TEST_REDIS_PASSWORD` 后执行，并使用唯一测试前缀；清理范围只限该前缀，不会清库。
