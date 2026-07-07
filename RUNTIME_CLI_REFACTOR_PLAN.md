# bank-agent-runtime / bank-agent-cli 改造计划

## 目标

`bank-agent-runtime` 和 `bank-agent-cli` 作为统一 SDK/脚手架体系同步演进。runtime 的能力修改必须同步到 cli 模板、示例、Docker 启动脚本和生成项目规范，避免生成出来的智能体项目继续使用旧逻辑。

最终目标：

- runtime 提供稳定、统一、可治理的智能体执行底座。
- cli 生成的智能体项目默认符合 runtime 新规范。
- Docker 部署通过环境变量注入环境相关配置，不在 SDK 或生成代码里硬编码服务器地址。
- `gen-b` 保持为同事原本的前后端项目，不把 runtime/cli 改造混入 `gen-b` 内部。

## 仓库组织

采用父仓库 + submodule 方案：

```text
genb/
├── AGENTS.md
├── PROJECT_OVERVIEW.md
├── CLEANUP_GUIDE.md
├── RUNTIME_CLI_REFACTOR_PLAN.md
├── bank-agent-project/
│   ├── bank-agent-cli/        # submodule: szharf/bank-agent-cli
│   └── bank-agent-runtime/    # submodule: szharf/bank-agent-runtime
└── gen-b/                     # submodule: kdanotadc/gen-b
```

这样 `genb` 负责组织关系和总体文档，`gen-b` 仍然保持原仓库、原前后端项目结构。

## 阶段一：收敛核心执行模型

### 1. 统一执行入口

现状：

- `BaseEmployeeAgent` 和 `AgentRuntimeCore` 是两套执行链。
- HTTP `/invoke` 走 `agent.handle()`。
- `policy -> memory -> reasoning -> tools -> llm -> approval -> audit` 这套链路没有成为统一入口。

目标：

- 新增标准数据结构：
  - `TaskEnvelope`
  - `RuntimeContext`
  - `ExecutionResult`
- 所有入口统一为：

```text
TaskEnvelope -> RuntimeContext -> AgentRuntimeCore.execute() -> ExecutionResult
```

runtime 修改：

- `bank_agent_runtime/base.py`
  - `handle()` 适配 `TaskEnvelope`。
  - 保留旧任务 dict 兼容层。
  - 队列任务和同步任务都返回或记录 `ExecutionResult`。
- `bank_agent_runtime/runtime/core.py`
  - 成为唯一主执行管线。
  - policy、memory、reasoning、tools、llm、approval、audit 按固定阶段执行。
- `bank_agent_runtime/runtime/context.py`
  - 补齐 request id、tenant id、user id、agent id、trace id、权限上下文。

cli 修改：

- 模板生成的 `agent.py` 使用新 `TaskEnvelope`。
- 示例 handler 返回 `ExecutionResult` 兼容结构。
- 文档说明旧版 dict task 的兼容边界。

验证：

- 新增 runtime 单测：旧 dict task 和新 TaskEnvelope 都能执行。
- 新增 cli 生成项目测试：生成项目的 `/invoke` 能走统一 runtime pipeline。

## 阶段二：HTTP API 标准化

### 2. 标准错误模型

现状：

- `/invoke` 捕获异常后倾向返回业务 JSON。
- HTTP 状态码可能仍是 200。

目标：

- 成功：2xx + `ExecutionResult`
- 客户端错误：4xx
- 服务端错误：5xx
- 错误体统一：

```json
{
  "success": false,
  "error": {
    "code": "POLICY_DENIED",
    "message": "任务被策略拒绝",
    "details": {},
    "traceId": "..."
  }
}
```

runtime 修改：

- `bank_agent_runtime/app.py`
  - 使用 `HTTPException` 或统一异常处理器。
  - 区分 validation、policy denied、auth failed、tool timeout、llm failed。
- 新增 `bank_agent_runtime/errors.py`。

cli 修改：

- 生成项目 README 补充错误码说明。
- `test_page.py` 按 HTTP 状态码展示错误。

验证：

- FastAPI TestClient 覆盖 200/400/401/403/500。

### 3. 三类健康状态拆分

现状：

- `/health` 把 `offline` 当 unhealthy。
- 业务状态和进程健康混在一起。

目标：

- `/health/live`：进程存活。
- `/health/ready`：依赖可用。
- `/status`：智能体业务状态，包含启动、停止、暂停、下线。

runtime 修改：

- `bank_agent_runtime/app.py`
- `bank_agent_runtime/observability/health.py`

cli 修改：

- `Dockerfile` HEALTHCHECK 使用 `/health/ready`。
- `docker_run.sh` 检查 Docker health。
- 文档说明 agent status 不等于 container health。

验证：

- agent offline 时 `/health/live` 仍 healthy。
- 依赖不可用时 `/health/ready` degraded/unhealthy。
- `/status` 返回业务状态。

## 阶段三：配置和 Docker 注入

### 4. 去除公网网关硬编码

现状：

- runtime 默认 `http://47.116.69.17:8002`。
- cli 模板、spec 示例、测试页也有硬编码。

目标：

- SDK 不包含真实服务器地址。
- Docker 通过 `.env` 或 `-e` 注入：

```env
ALAYA_BASE_URL=http://47.116.69.17:8002
ALAYA_PROVIDER=minimax
ALAYA_MODEL=MiniMax-M2.7-highspeed
ALAYA_TIMEOUT=60
LLM_CACHE_ENABLED=true
LLM_DAILY_BUDGET=100000
LLM_MONTHLY_BUDGET=3000000
```

runtime 修改：

- `bank_agent_runtime/llm/factory.py`
  - `ALAYA_BASE_URL` 不再默认公网地址。
  - 启用 alaya 且未配置 base url 时明确报错。
- `bank_agent_runtime/llm/adapters/alaya.py`
  - 构造函数不再默认公网地址。
  - 初始化时校验 `base_url`。

cli 修改：

- `bank_agent_cli/core/spec.py`
  - 默认值改为空或 localhost 占位。
- `templates/default/agent.py.j2`
  - 删除 `ALAYA_GATEWAY_BASE_URL` 常量。
- `templates/default/.env.example.j2`
  - 新增 LLM 环境变量示例。
- `templates/default/scripts/docker_run.sh.j2`
  - 增加 `--env-file .env`。
- `templates/default/docker-compose.yml.j2`
  - 保持 `env_file: .env`。
- `templates/default/test_page.py.j2`
  - 从 env 读取模型地址。
- `spec_examples/*.yaml`
  - 移除真实公网 IP。

验证：

- 不设置 `ALAYA_BASE_URL` 时初始化失败且错误清晰。
- 设置 `ALAYA_BASE_URL` 后正常初始化。
- CLI 生成项目中不再出现 `47.116.69.17:8002`。

## 阶段四：安全底座

### 5. 安全中间件

现状：

- `security.py` 更像工具函数。
- 请求链路没有强制认证、鉴权、输入限制、敏感日志脱敏。

目标：

- API Key/JWT/mTLS hook。
- 请求体大小限制。
- tenant/user/agent 权限上下文。
- 敏感字段日志脱敏。
- 工具调用权限校验。
- prompt injection 基础防护接口。

runtime 修改：

- 新增 `bank_agent_runtime/security/middleware.py` 或保持当前模块下新增中间件。
- `create_agent_app()` 支持安全配置。
- `RuntimeContext` 注入安全主体。

cli 修改：

- `config.yaml.j2` 新增 security 配置段。
- `.env.example` 增加 API key/JWT 配置占位。
- README 说明本地开发可关闭，生产默认开启。

验证：

- 未认证请求返回 401。
- 无权限工具调用返回 403。
- 日志不输出敏感字段。

## 阶段五：运行质量优化

### 6. CORS 配置

现状：

- `allow_origins=["*"]`。

目标：

- 开发环境可放宽。
- 生产环境必须显式配置 origin。

runtime 修改：

- `create_agent_app(cors_origins=...)`
- 从 env/config 读取 `CORS_ORIGINS`。

cli 修改：

- `.env.example` 增加 `CORS_ORIGINS`。
- `config.yaml.j2` 增加 cors 配置。

验证：

- 未配置生产 origin 时启动告警或拒绝 credentials + wildcard 组合。

### 7. 修 metrics bug

现状：

- `success_rate` 被赋值为 `avg_processing_time`。

目标：

- 正确计算：

```text
success_rate = tasks_completed / tasks_received
```

runtime 修改：

- `bank_agent_runtime/app.py`
- `bank_agent_runtime/observability/metrics.py`

验证：

- 单测覆盖成功、失败、零任务三种情况。

### 8. 生命周期钩子接入

现状：

- `on_start/on_stop/on_leave_start` 有定义，但未成为状态切换必经步骤。

目标：

- `start_work()` 调 `on_start()`。
- `stop_work()` 调 `on_stop()`。
- 休假/暂停调用对应 hook。
- hook 失败时状态不应假成功。

runtime 修改：

- `bank_agent_runtime/base.py`

cli 修改：

- 生成模板保留可覆盖 hook 的示例注释。

验证：

- 单测确认 hook 被调用。
- hook 异常时返回标准错误。

### 9. LLM Client 生命周期优化

现状：

- `AlayaGatewayAdapter` 每次请求创建 `httpx.AsyncClient`。

目标：

- adapter 复用 AsyncClient。
- 支持 close/aclose。
- 支持 timeout、retry、backoff、限流、熔断。

runtime 修改：

- `bank_agent_runtime/llm/adapters/alaya.py`
- `bank_agent_runtime/llm/service.py`

cli 修改：

- 生成项目在 app shutdown 时关闭 LLM client。
- `.env.example` 增加 retry/timeout 配置。

验证：

- 单测确认复用 client。
- 模拟超时和 5xx 重试。

### 10. PostgreSQL async 化和依赖补齐

现状：

- async 方法里使用同步 `psycopg2`。
- `pyproject.toml` 未声明 PostgreSQL 依赖。

目标：

- 短期：补 `psycopg2-binary` extra。
- 中期：改 `asyncpg` + connection pool。

runtime 修改：

- `pyproject.toml`
  - 增加 extras：

```toml
[project.optional-dependencies]
postgres = ["asyncpg>=0.29"]
dev = ["pytest", "pytest-asyncio", "httpx"]
```

- `memory/postgresql_storage_v2.py`
  - 改 asyncpg 或新增 asyncpg 版本，保留旧实现兼容。

cli 修改：

- `requirements.txt.j2` 根据 memory backend 加入 extras。
- Dockerfile 安装正确依赖。

验证：

- PostgreSQL 集成测试。
- 并发查询不阻塞事件循环。

### 11. OpenTelemetry 接入

现状：

- tracing/metrics 是内存实现。

目标：

- 支持 OpenTelemetry trace/metrics/log correlation。
- 保留当前轻量内存实现作为本地调试。

runtime 修改：

- 新增 observability provider：
  - `memory`
  - `opentelemetry`
- FastAPI instrumentation。
- trace id 注入 `RuntimeContext`。

cli 修改：

- `.env.example` 增加 OTEL 配置。
- Docker 传递 OTEL endpoint。

验证：

- 本地关闭 OTEL 不影响运行。
- 开启后请求产生 span。

## 阶段六：高级治理能力

### 12. 持久化任务和工作流状态

现状：

- Operator workflow 是轻量 asyncio 编排。
- 没有 checkpoint、resume、retry、human approval 持久化。

目标：

- WorkflowRun 表/存储。
- StepRun 状态。
- checkpoint。
- retry policy。
- resume。
- human approval interrupt。

runtime 修改：

- `operator_sdk/orchestrator.py`
- 新增 workflow store 接口。
- 新增 human approval 状态模型。

cli 修改：

- workflow yaml 支持 retry、timeout、approval。
- 生成示例 workflow。

验证：

- 失败后可 resume。
- 人审暂停后可继续。

### 13. Policy 配置化

现状：

- Policy rule 是 Python callable。

目标：

- 支持 YAML/JSON DSL。
- 规则版本化。
- 命中记录可审计。
- Python callable 只作为高级扩展。

runtime 修改：

- `policy/engine.py`
- 新增 DSL parser。

cli 修改：

- 生成 `policies/*.yaml`。
- 示例从 Python rule 改为 YAML rule。

验证：

- policy 文件加载、命中、版本记录。

### 14. Memory 治理

现状：

- 记忆能力偏通用。

目标：

- tenant/user/agent namespace 强制隔离。
- 数据分类分级。
- TTL/retention job。
- 删除留痕。
- 检索权限过滤。
- 可选向量检索。

runtime 修改：

- `memory/service.py`
- `memory/postgresql_storage_v2.py`
- RuntimeContext 与 memory 绑定权限上下文。

cli 修改：

- memory 配置模板增加 tenant strategy、retention policy。

验证：

- A 用户不能检索 B 用户记忆。
- 过期记忆不可召回。

## 实施顺序

1. 配置和硬编码治理：风险低、收益高，先做。
2. HTTP 错误模型、健康状态、metrics、生命周期 hook。
3. 统一执行入口。
4. 安全中间件。
5. LLM client 生命周期、PostgreSQL async、OpenTelemetry。
6. workflow 持久化、policy DSL、memory governance。

## 不做事项

- 不修改 `D:\code\opencode\genb\gen-b` 内部代码。
- 不把 `gen-b` 的构建产物、`node_modules`、`target/classes` 纳入父仓库。
- 不在 SDK 或 CLI 模板中写真实服务器地址。
- 不在 runtime 中暴露或持久化详细模型思维链。
