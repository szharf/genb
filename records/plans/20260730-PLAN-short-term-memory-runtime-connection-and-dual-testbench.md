# 短期记忆运行联通与双模式测试台任务计划

> 日期：2026-07-30
> 范围：GenB核心组件控制面、独立短期记忆服务、管理端、专用测试智能体
> 状态：已完成

## 1. 本轮目标

把上一轮“契约与服务分别完成、暂不连通”推进为真实运行闭环，并保留两条用途不同、不能互相替代的测试路径：

1. **管理员服务直测**：管理员从GenB核心组件详情页直接选择已注册且启用的服务实现和已发布配置进行测试；不要求智能体、服务凭证或组件绑定，但必须具有`component.test`权限，请求由GenB签发短时可信测试身份并记录审计。
2. **智能体绑定测试**：选择已有启用绑定的智能体，使用该智能体唯一的长期服务凭证；GenB必须依次校验用户有权使用智能体、凭证与`agentId`一致、绑定启用、Implementation启用、配置已发布，然后签发短时Actor Token调用组件服务。

两条路径都必须真实调用`short-term-memory-service`，通过本地Redis保存和恢复数据；不部署公网服务器。

## 2. 已确认的当前问题

- 当前管理页面只有一个测试表单，并且只列出已启用绑定。
- 当前`/v1/core-components/{componentCode}/tests:run`强制要求`agentId + serviceCredential`。
- 当前HTTP调用器固定调用旧Control System路径，不能调用独立短期记忆服务路径。
- 独立服务当前相信调用者直接填写的`X-Tenant-Id/X-Agent-Id/X-User-Id`，只适合上一轮Swagger独立测试，不满足正式联通安全要求。
- 独立服务端口`18705`当前未启动；Redis、GenB后端、管理端和客户端正在运行。

## 3. 公开接口与安全边界

### 3.1 管理员服务直测

- 新接口：`POST /api/v1/core-components/{componentCode}/service-tests:run`
- 权限：`component.test`
- 输入：Implementation、已发布配置、`taskId`、`sessionId`、测试消息。
- 不输入：智能体、服务凭证、任意身份Header。
- GenB行为：校验实现/配置状态与归属，签发最多5分钟的`COMPONENT_ADMIN_TEST` Actor Token，使用固定测试agent标识和当前管理员userId调用服务，写入成功/失败审计。
- 组件服务行为：只接受GenB签名有效、受众正确、组件和scope正确的管理员测试Token；不接受浏览器自报身份。

### 3.2 智能体绑定测试

- 保留接口：`POST /api/v1/core-components/{componentCode}/tests:run`
- 输入：`agentId + serviceCredential + taskId + sessionId + message`。
- GenB行为：复用长期服务凭证与绑定会话链，按绑定解析Implementation/配置并签发`COMPONENT_SESSION` Actor Token。
- 组件服务行为：校验Actor Token；校验服务凭证有效且属于Token中的`agentId`；校验组件和read/write scope。

### 3.3 服务实现调用适配

- Implementation增加显式`invocationAdapter`，禁止根据服务名、URL或接口版本猜调用方式。
- 本轮支持`CONTROL_SYSTEM_MEMORY_V1`（旧Control System兼容路径）和`SHORT_TERM_MEMORY_V1`（独立服务接口）。
- 实际建表只增加普通列，不创建物理外键。

## 4. 前端组件边界

- `CoreComponentTestBench.vue`：只负责“服务直测/智能体测试”模式切换和结果组合。
- `CoreComponentServiceTestForm.vue`：管理员直测表单；只接收Implementation、配置和运行状态，向上发出直测payload。
- `CoreComponentTestForm.vue`：只负责智能体、服务凭证和绑定测试输入。
- `CoreComponentTestResult.vue`：复用统一结果展示，并明确展示测试模式、Implementation、配置和运行耗时。
- `useCoreComponentTestBench.js`：分别暴露`runServiceTest`与`runAgentTest`，集中处理请求状态和错误。
- `testBenchModel.js`：纯函数构造两类payload，承担trim、必填项和`taskId/sessionId`格式校验。

数据流坚持props down / events up；路由详情页只提供Implementation、配置和绑定数据，不持有测试表单内部状态。

## 5. TDD纵向切片

### Slice 1：管理员可无绑定直测

1. RED：管理员在没有智能体绑定时提交有效Implementation/配置可得到真实测试结果。
2. GREEN：新增直测请求、实现解析、短时管理员测试Token和审计。
3. RED：禁用实现、草稿配置、跨组件实现或无权限用户必须失败。
4. GREEN：补齐fail-closed校验。

### Slice 2：独立服务可信身份

1. RED：正式联通模式下，只有自报`X-*` Header的请求返回401。
2. GREEN：实现GenB JWKS Actor Token校验和组件/scope校验。
3. RED：绑定模式缺少/伪造服务凭证、凭证与agent不一致返回401/403；管理员测试Token不要求智能体凭证。
4. GREEN：增加GenB introspection Adapter和两类Token策略。

### Slice 3：独立短期记忆调用适配

1. RED：`SHORT_TERM_MEMORY_V1`能使用`taskId`准备上下文、提交回合并返回消息数量。
2. GREEN：增加显式Adapter路由，保留旧Control System Adapter回归。
3. RED：超时、非2xx、无效响应必须返回稳定错误且不泄漏凭证。
4. GREEN：补齐错误与审计。

### Slice 4：管理端双模式测试台

1. RED：纯模型测试证明服务直测payload不含`agentId/serviceCredential`，智能体payload必须包含并清空明文凭证。
2. GREEN：新增双模式组件、API和双语文案。
3. 构建：Node逻辑测试、`vue-tsc`、中文/英文生产构建。

### Slice 5：真实注册、绑定和验收

1. Redis模式启动独立短期记忆服务。
2. 在远程开发库对应的GenB页面注册`SHORT_TERM_MEMORY_V1`实现。
3. 创建并发布测试配置。
4. 为专用测试智能体创建或复用启用绑定。
5. 生成或轮换该智能体唯一的长期服务凭证。
6. 页面执行管理员服务直测：首次调用0条上下文，再次使用相同`taskId`、新`sessionId`应召回上一轮。
7. 页面执行智能体绑定测试：同样验证写入、跨session恢复。
8. 负向验证：停用绑定后智能体测试失败，但管理员服务直测仍成功；随后恢复绑定。
9. 验证服务缺少Token、自报Header、错误凭证、错误agent均失败。
10. 检查审计记录、Redis数据隔离和浏览器控制台。

## 6. 里程碑与验收门禁

| 里程碑 | 工作 | 状态 | 门禁 |
|---|---|---|---|
| M0 | 当前链路盘点与计划 | 已完成 | 两条测试路径、安全边界、组件边界已写清 |
| M1 | GenB管理员服务直测后端 | 已完成 | 后端行为测试通过，无绑定可测且状态校验关闭 |
| M2 | 独立服务可信身份与调用Adapter | 已完成 | 正/负身份矩阵、真实HTTP/Redis通过 |
| M3 | 管理端双模式测试台 | 已完成 | 纯模型测试、双语构建通过 |
| M4 | 远程开发库注册与专用智能体绑定 | 已完成 | 只追加/更新本任务测试记录，不删历史数据 |
| M5 | 浏览器逐点击与端到端验收 | 已完成 | 两条路径、跨session、停绑负测和恢复通过 |
| M6 | 操作手册、报告、索引与提交 | 已完成 | 零基础手册与实际页面一致，精确提交 |

## 7. 完成标准

- 页面明确提供“服务直测”和“智能体绑定测试”，用户能看懂两者差异。
- 服务直测不依赖任何智能体绑定或服务凭证，但只能由有权限管理员经GenB发起。
- 智能体测试必须通过凭证、agent、绑定、Implementation和配置全部校验。
- 两条路径都真实调用独立短期记忆服务，完成写入和跨session恢复。
- 独立服务正式模式不再相信外部直接提交的身份Header。
- 旧Control System测试链不回归。
- 新增数据库结构无物理外键；远程开发数据不执行破坏性删除。
- 后端、Python、前端自动化和真实浏览器验收通过。
- 更新逐点击操作手册，写清每个按钮、输入值、来源、原因、预期和排错方法。

## 8. 回滚与风险控制

- `invocationAdapter`具有旧实现默认值，已有实现不因本轮升级失效。
- 新直测接口是新增入口，不改变智能体正式会话接口。
- 独立服务保留显式开发测试认证模式，但正式联通启动必须使用`genb`模式；开发模式不得用于绑定验收。
- 注册和绑定使用唯一测试编码；不删除或覆盖其他团队Implementation、配置和绑定。
- 凭证、数据库密码、Redis密码、内部Token和Actor Token不写入文档、截图、Git或普通日志。
