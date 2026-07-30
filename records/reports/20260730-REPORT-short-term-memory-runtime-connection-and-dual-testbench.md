# 短期记忆运行联通与双模式测试台实施报告

> 日期：2026-07-30
> 结论：已完成并通过本地真实联通验收

## 1. 完成结果

独立短期记忆服务已经从“只可Swagger独立测试”推进为GenB真实运行Implementation。GenB管理端现在提供两种明确分开的测试方式：

- `SERVICE_DIRECT`：管理员直接测试注册服务，不依赖智能体、服务凭证或绑定。
- `AGENT_BINDING`：使用智能体长期服务凭证并强制校验启用绑定。

两条路径都实际调用`http://127.0.0.1:18705`，数据保存到本地Redis DB 13；正式服务使用`genb`身份模式，不接受调用者自报tenant/agent/user。

## 2. 主要实现

### GenB后端

- 新增`POST /api/v1/core-components/{componentCode}/service-tests:run`。
- 新增管理员测试会话，校验Implementation归属/状态和配置归属/发布状态，签发5分钟`COMPONENT_ADMIN_TEST` Actor Token。
- Implementation新增`invocationAdapter`普通列：旧数据默认`CONTROL_SYSTEM_MEMORY_V1`，新服务使用`SHORT_TERM_MEMORY_V1`。
- 智能体请求增加`taskId`，与`sessionId`明确分离。
- HTTP调用器保留旧Control System路径，同时支持独立短期记忆`context:prepare`和`turns:commit`。

### 独立短期记忆服务

- 新增`development_headers`和`genb`两种显式认证模式。
- `genb`模式校验GenB JWKS签名、issuer、audience、有效期、组件和scope。
- `COMPONENT_SESSION`必须同时 introspect 服务凭证并检查凭证`agentId`与Actor Token一致。
- `COMPONENT_ADMIN_TEST`不接收智能体服务凭证，由短时签名Token提供可信隔离身份。

### 管理端

- “独立测试台”内新增“管理员服务直测”和“智能体绑定测试”子页签。
- 服务直测表单只包含Implementation、已发布配置、taskId、sessionId和消息。
- 智能体表单保留智能体、凭证管理，并新增taskId。
- 结果卡显示`SERVICE_DIRECT`或`AGENT_BINDING`。
- 注册Implementation时显式选择调用适配。
- 中英文文案和构建均已补齐。

## 3. 远程开发库追加数据

只追加或更新本任务测试记录，没有删除历史数据：

| 类型 | 结果 |
|---|---|
| 契约 | `SHORT_TERM_MEMORY / 1.0.0 / PUBLISHED`，7个操作 |
| Implementation | ID 4，`standalone-short-term-memory-v1 / REGISTERED / SHORT_TERM_MEMORY_V1` |
| 配置 | ID 6，`dual-testbench-default / v1 / PUBLISHED` |
| 测试智能体 | `standalone-memory-test-agent` |
| 绑定 | ID 6，指向Implementation 4/配置6，最终状态`ENABLED` |
| 服务凭证 | 专用智能体保持一份当前`ACTIVE`长期凭证；验收过程发生安全轮换 |

`component_implementations`只新增普通`invocation_adapter`列。实体的逻辑关系仍使用`ConstraintMode.NO_CONSTRAINT`，没有新增物理外键。

## 4. 真实功能验收

### 管理员服务直测

- 第一次：`contextMessageCount=0`，`messageCount=2`。
- 同一taskId、新sessionId第二次：`contextMessageCount=2`，`messageCount=4`。
- 实际Implementation：`standalone-short-term-memory-v1`。

### 智能体绑定测试

- 第一次：`contextMessageCount=0`，`messageCount=2`。
- 同一taskId、新sessionId第二次：`contextMessageCount=2`，`messageCount=4`。
- 测试模式：`AGENT_BINDING`。

### 负向矩阵

- 服务只收到伪造`X-Tenant-Id/X-Agent-Id/X-User-Id`：HTTP 401。
- 临时停用绑定：智能体测试HTTP 400。
- 同期管理员服务直测：HTTP 200。
- 绑定最终恢复：`ENABLED`。

### 浏览器

- 两个子页签均通过真实点击、选择、输入、凭证轮换和提交。
- 页面控制台错误：0。
- 截图：`records/reports/assets/20260730-dual-testbench.png`。

## 5. 自动化验证

| 范围 | 结果 |
|---|---|
| GenB后端全量 | 124 passed，0 failed，0 skipped |
| HTTP调用Adapter专项 | 4 passed |
| CoreComponent测试服务专项 | 4 passed |
| 独立短期记忆服务（含真实Redis） | 10 passed |
| 管理端全部纯逻辑测试 | 全部通过 |
| 中文生产构建 | 通过 |
| 英文生产构建 | 通过 |
| 真实浏览器 | 服务直测、智能体绑定测试均通过 |

## 6. 当前运行状态

| 端口 | 服务 | 状态 |
|---:|---|---|
| 6379 | Redis | 运行中 |
| 8581 | GenB后端 | 运行中 |
| 9000 | GenB管理端源码开发服务 | 运行中 |
| 9100 | 本地统一入口/Nginx | 运行中（已构建旧产物不包含本次源码页面） |
| 18705 | 独立短期记忆服务 | 运行中，Redis + GenB身份模式 |

本轮没有部署公网环境。查看新页面应使用`http://127.0.0.1:9000/genb/core-components/SHORT_TERM_MEMORY`；`9100`需要以后重新构建部署管理端产物才会包含本次变化。

## 7. 文档

- 任务计划：`records/plans/20260730-PLAN-short-term-memory-runtime-connection-and-dual-testbench.md`
- 最新逐点击手册：`docs/operation/SHORT_TERM_MEMORY_RUNTIME_CONNECTION_AND_DUAL_TESTBENCH_GUIDE.md`
- 历史未连通手册已增加阶段提示。
