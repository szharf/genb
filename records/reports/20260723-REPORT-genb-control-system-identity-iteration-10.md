# GenB与Control System身份契约 Iteration 10 实施报告

## 任务：完成RS256 Actor Token、JWKS、服务凭证内省与Control System真实Adapter

### 1. 背景

Iteration 9已经交付Short-term Memory执行面，但只能使用本地凭证文件和单个RSA公钥。GenB现有Component Session使用从登录密钥派生的HMAC签名，claims缺少`tenantId/iss/aud/components`，服务凭证也没有可供Control System调用的内省Interface，因此真实智能体不能安全接入。

### 2. 目标

建立GenB与Control System之间可独立验证、默认拒绝失败请求的身份契约：GenB负责签发Actor Token和判定服务凭证状态，Control System只持公钥并通过受保护HTTP Interface获得最小凭证身份。

### 3. 范围

本次完成：

- 保持现有Component Session响应兼容，将其中Actor Token从HS256升级为RS256。
- Actor Token增加`kid/iss/aud/tenantId/components/nbf`，`sub`和`userId`使用同一可信用户标识。
- 新增`GET /api/.well-known/jwks.json`，只发布RSA公钥参数。
- 新增`POST /api/v1/internal/service-credentials:introspect`，使用独立内部Bearer Token保护。
- 内省有效、篡改、过期、吊销和内部调用认证矩阵。
- Control System新增GenB HTTP内省Adapter和JWKS Actor Token Adapter。
- Short-term Memory scope统一为`component:short-term-memory:read|write|delete`。
- 增加生产HTTPS门禁、弱RSA密钥拒绝、公私钥匹配和JWT时序/主体约束。

本次不做：

- 不部署，不重启当前本地服务，不修改远程PostgreSQL。
- 不新增表、迁移或物理外键。
- 不实现多租户目录、自动密钥轮换、Actor Token在线吊销和内省/JWKS缓存。
- 不创建真实测试智能体，不声称已完成智能体端到端演示。

### 4. 完成标准

- [x] 组件会话返回带`kid`的RS256 Actor Token，默认有效期5分钟。
- [x] JWKS可独立验签Token，响应不包含`d/p/q`等私钥参数。
- [x] `tenantId/userId/agentId/sessionId/components`均来自GenB可信状态，而非请求体。
- [x] 内部认证错误返回401；无效、过期或吊销凭证返回`active=false`且不泄露hash。
- [x] Control System通过HTTP/JWKS Adapter构造`InvocationIdentity`。
- [x] 未知`kid`、GenB 503、畸形响应、主体不一致和超长Token时效均fail-closed。
- [x] GenB与Control System全量测试通过。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对HMAC签发、claims、scope和租户来源差距 | 已完成 | 确认两个执行面Adapter seam |
| 2 | RED→GREEN：RS256 Actor Token与JWKS | 已完成 | JWKS重建RSA公钥并独立验签 |
| 3 | RED→GREEN：服务凭证内省 | 已完成 | 有效/篡改/过期/吊销/内部认证矩阵 |
| 4 | RED→GREEN：Control System HTTP/JWKS Adapter | 已完成 | 公开记忆Interface完成身份构造 |
| 5 | scope统一、安全加固和双项目回归 | 已完成 | 21项Python测试、108项Java测试 |
| 6 | 自审、报告、索引和精确提交 | 已完成 | GenB `ef0a627`，父仓库 `add0e13` |

### 6. 当前进度

- 已完成：GenB签发面、JWKS发布面和凭证内省面。
- 已完成：Control System的GenB连接模式与本地测试模式并存。
- 已完成：设计指南中的实际路径、请求字段和scope已同步。
- 待下一迭代：生成专用测试智能体，注册/绑定Short-term Memory并完成A/B逻辑实例隔离演示。

### 7. 验收记录

GenB：

- [x] Maven全量测试：`108 tests, 0 failures, 0 errors, 0 skipped`。
- [x] 组件访问集成测试实际签发RS256 Token，从JWKS重建RSA公钥并验签。
- [x] 内省有效、缺失/错误内部Token、篡改、吊销和过期行为通过。
- [x] 1024-bit RSA私钥被拒绝，最小强度为2048 bit。
- [x] 使用独立`target-iteration10`构建目录验证，没有停止正在运行的本地GenB服务；该目录已被Git忽略且未提交。

Control System：

- [x] `pytest -q`：`21 passed`。
- [x] `compileall`：通过。
- [x] OpenAPI重新导出并与运行时schema一致。
- [x] 真实Redis集成继续通过，测试键残留为0。
- [x] GenB内省/JWKS Adapter成功链路、未知`kid`和503 fail-closed通过。

提交：

- GenB `create-genB`：`ef0a627`（`feat: publish component identity contracts`）。
- 父仓库 `codex/genesis-genc-authorization-docs-20260720`：`add0e13`（`feat: connect control system to genb identity`）。

### 8. 风险和遗留问题

1. GenB目前没有正式租户目录，`tenantId`暂由受信环境变量`GENB_TENANT_ID`提供，只能视为单租户过渡Adapter。
2. GenB需要配置`COMPONENT_ACTOR_KEY_ID`、PKCS#8私钥路径和`CONTROL_SYSTEM_INTERNAL_TOKEN`；代码不会生成生产默认秘密。
3. Control System生产连接要求`GENB_BASE_URL`使用HTTPS，但尚未执行证书、网络ACL和密钥轮换演练。
4. JWKS与内省当前不缓存，GenB故障时立即fail-closed；性能和短时缓存策略需在真实压测后确定。
5. 静态活动密钥只支持单个`kid`；多密钥并行发布、轮换宽限期和旧Token过渡仍待实现。
6. 本轮没有部署，因此当前正在运行的本地GenB仍是旧进程；只有按新环境变量重启新代码后才会提供新Interface。
