# Control System Short-term Memory Iteration 9 实施报告

## 任务：交付不依赖旧 Runtime SDK 的短期记忆首条真实纵向切片

### 1. 背景

GenB 已完成五大系统/14个核心组件目录、治理控制面和管理端操作，但“短期记忆”仍只有控制面记录，没有由 Control System 拥有并通过独立 HTTP Interface 提供的真实执行面。旧 Runtime SDK 仅作为参考，不再嵌入每个智能体；组件能力需要可独立部署、统一治理并由智能体按授权调用。

### 2. 目标

新建 `control-system-service`，实现 Short-term Memory 的提交、上下文准备和会话清理，让后续测试智能体可以通过稳定接口使用短期记忆，并为 Long-term Memory 和其余 Control System 组件建立可复用的模块边界、安全身份与存储模式。

### 3. 范围

本次完成：

- `turns:commit`、`context:prepare`、session clear 三个公开 Interface。
- 服务凭证与 RS256 Actor Token 双凭证校验，强制 agent/component/scope 一致性。
- tenant/user/agent/session 四维隔离，身份信息只来自已验证凭证。
- 同作用域幂等、冲突检测、最近完整回合预算裁剪和持久化前敏感信息脱敏。
- In-memory 与 Redis 两个 `SessionStore` Adapter；Redis 使用 Lua 原子提交、TTL 和 HMAC 键。
- live/ready/version、OpenAPI、环境配置示例、本地启动工厂及自动测试。

本次不做：

- Long-term Memory、对话摘要、完整 RAG 和模型调用。
- GenB 真实 Actor Token/JWKS、生产服务凭证内省和测试智能体联调。
- 管理端独立测试台、部署和远程 PostgreSQL 变更。

### 4. 完成标准

- [x] 双凭证缺失或无效返回401，授权不匹配返回403。
- [x] 同一身份提交后可召回；tenant/user/agent/session 任一变化均隔离。
- [x] 同一幂等键与相同内容不重复写，不同内容返回409。
- [x] 幂等键本身也按完整四维作用域隔离，跨用户/会话不会互相冲突。
- [x] Redis 写入具有原子性、TTL，键中不出现原始身份值。
- [x] 密码、API Key、Secret 和 Bearer Token 在持久化前脱敏。
- [x] 旧 Runtime SDK 在新服务依赖和源码中为零引用。
- [x] OpenAPI 与应用实时导出一致，自动测试与真实本地 Redis 验证通过。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对设计、身份契约和现有运行环境 | 已完成 | 复用现有 Python 环境；Redis 返回 `PONG` |
| 2 | 以测试驱动实现双凭证与首个 commit/prepare 切片 | 已完成 | Interface 测试由失败转为通过 |
| 3 | 实现隔离、幂等、预算、脱敏和 clear | 已完成 | 接口与安全测试覆盖关键分支 |
| 4 | 实现 Redis Adapter 和真实集成测试 | 已完成 | Lua、TTL、HMAC 键及精确清理通过 |
| 5 | 补齐健康检查、OpenAPI、README 和启动门禁 | 已完成 | 合同测试、生产 fail-closed 测试通过 |
| 6 | 自审、回归、记录和精确提交 | 已完成 | 实现提交 `3f7f631` |

### 6. 当前进度

- 已完成：Control System Short-term Memory 的本地/测试纵向切片。
- 已完成：公开 Interface、Identity Module、Short-term Memory Module、两个 Store Adapter 与 OpenAPI。
- 已完成：提交前自审发现并修复 Redis 幂等键仅按 agent 隔离的问题，改为完整四维作用域。
- 阻塞：真实智能体联调仍受 GenB 当前 Actor Token 契约限制，不能把本地凭证 Adapter 当作生产实现。

### 7. 验收记录

执行环境：Windows，本地 Redis `127.0.0.1:6379`，测试数据库 DB 15；密码只通过环境变量注入，未写入代码或报告。

- [x] `python -m pytest -q`：`16 passed`。
- [x] `python -m compileall -q src tests scripts`：通过。
- [x] OpenAPI 重新导出后合同测试：文件与运行时 schema 完全一致。
- [x] 真实 Redis 集成：提交、重复请求、冲突、跨作用域同幂等键、读取、TTL、HMAC 键和清理通过。
- [x] 测试后扫描 `genb:cs:test:*`：残留键为0。
- [x] 旧 SDK 扫描：`LEGACY_SDK_NO_MATCH`。
- [x] 硬编码敏感信息扫描：无真实凭证；README 只包含 `<local test password>` 占位符。
- [x] `git diff --cached --check`：通过。

实现提交：`3f7f631cbe057ef30d84dbd8b03382890bb7b1e4`。

### 8. 风险和遗留问题

1. GenB Iteration 5 当前 Component Session 使用派生对称密钥 JWT，claims 缺少本服务要求的 `tenantId`、`iss`、`aud`、`components`，暂时不能直接接入。
2. 本地启动工厂只允许 `APP_ENV=local|test`；生产环境会 fail-closed。这是安全门禁，不是生产部署能力。
3. 下一迭代应先完成 GenB RS256 Actor Token、JWKS 发布/轮换和服务凭证内省契约，再做真实测试智能体调用。
4. 当前 JWT 校验使用单个本地 RSA 公钥，尚未实现按 `kid` 选择 JWKS 密钥；应在真实联调前补齐。
5. Long-term Memory、RAG、摘要、管理端测试台和用户可配置保存期限仍在后续里程碑中。
6. 本轮未部署、未修改远程 PostgreSQL，也没有创建任何数据库外键。
