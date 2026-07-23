# Short-term Memory Iteration 12实施报告

## 任务：完成管理测试台、动态配置、摘要与可观测性

### 1. 背景

Iteration 11已经用专用Test Agent贯通GenB组件会话、Control System和Redis，但短期记忆仍依赖进程启动参数，没有管理员可操作的独立测试台，也没有会话摘要、Runtime Inference调用和运行指标。上述缺口会让“页面可演示”和“智能体真实调用”形成两套行为，也无法证明发布配置能够约束数据面。

### 2. 目标

把Short-term Memory提升为一期可验收组件：管理员从GenB详情页使用真实绑定运行测试；Control只接受Actor Token绑定快照中的已发布配置；超阈值历史通过我方Runtime Inference Interface摘要；Redis保存摘要且阻止旧任务覆盖；健康、指标、日志和trace均不暴露正文或秘密。

### 3. 范围

本次完成：

- GenB新增`component.test`权限和`POST /v1/core-components/{componentCode}/tests:run`小Invoker。
- Vue详情页新增独立测试Tab，并拆分Form、Result、Feature容器和Composable。
- GenB新增受内部Bearer Token保护的已发布配置读取Interface，不返回`secretRefs`。
- Actor Token绑定快照在Control身份中携带`componentCode -> configVersionId`。
- Control新增严格动态配置Provider，按不可变配置ID短缓存并执行TTL、maxTurns和maxContextTokens。
- 新增Summary Port、Runtime Inference HTTP Adapter、Redis摘要Hash和`throughTurnId`乐观覆盖保护。
- 上下文返回摘要和未覆盖的新消息，摘要本身计入预算；Inference失败保留最近窗口并标记降级。
- 新增低基数Prometheus文本指标、结构化安全日志、Runtime降级健康和W3C`traceparent`透传。
- Runtime本地Fake显式支持`SESSION_SUMMARY`，仅用于自动化和本地验收；生产仍禁止Fake ready。
- 修复唯一绑定在停用后不能切换新配置的问题：原绑定记录重配置并写`BINDING_RECONFIGURED`审计。

本次没有新增数据库表或物理外键，没有部署生产环境。远程开发PostgreSQL只追加一份`iteration12-summary`已发布配置和审计记录；验收后把测试智能体绑定恢复到原配置。

### 4. 完成标准

- [x] 管理员测试Interface、非管理员拒绝、一次性凭证和错误脱敏通过。
- [x] 中文/英文页面构建及真实浏览器测试台通过，提交后密码框和页面正文不保留凭证。
- [x] 已发布配置控制TTL、窗口和预算；缺快照、草稿、非法值、超时/5xx全部fail-closed。
- [x] 摘要覆盖旧回合且不重复注入，旧任务不能覆盖新摘要。
- [x] Runtime失败不伪造成功摘要，不阻断最近窗口读取，并在ready中报告降级。
- [x] 指标只有固定operation/status/component/result标签，不包含用户、智能体、session、正文和凭证。
- [x] 真实GenB、Control、Runtime、远程PostgreSQL和Redis链路通过。
- [x] Redis验收键精确清理为0，三个临时进程精确停止，既有8581保持运行。

### 5. 执行结果

| 工作包 | 结果 | 证据 |
|---|---|---|
| WP1 管理测试Interface | 完成 | GenB专项及全量测试；响应不含服务凭证/Actor Token |
| WP2 Vue测试台 | 完成 | 9项Node TAP、中文/英文构建、Playwright真实页面 |
| WP3 动态配置 | 完成 | 配置Adapter 6项专项；GenB内部Interface发布态/鉴权测试 |
| WP4 摘要与可观测性 | 完成 | Control 33项、Runtime 33项、真实Redis和三服务E2E |
| 绑定状态机修复 | 完成 | 停用后原位重配置、同ID恢复、审计断言；ENABLED重复仍409 |

### 6. 自动化验收

- GenB后端：`115 tests, 0 failures, 0 errors, 0 skipped`。
- Control System：`33 passed`，真实Redis测试未跳过。
- Runtime System：`33 passed`。
- Test Agent：`8 passed`。
- GenB Console：9项Node TAP全部通过。
- GenB Console中文和英文生产构建均成功；仅有既有chunk体积warning。
- Control OpenAPI重新导出并与FastAPI运行契约完全一致；`compileall`通过。
- 新代码固定秘密、私钥正文和旧Runtime SDK模式扫描无命中。

### 7. 真实验收记录

- 管理页面：本地Vite代理到独立GenB 18581，Short-term Memory详情页测试台真实提交成功；截图保存在Git忽略的`.logs/iteration12/test-bench.png`。
- 动态摘要：Actor Token解析到`configVersionId=4`；两次commit后prepare返回`summaryStatus=AVAILABLE`、`throughTurnId=turn-1`和turn-2的两条最近消息。
- Runtime边界：Control通过`POST /api/v1/runtime-system/inference`和`capability=SESSION_SUMMARY`调用本地Runtime；本次用Fake仅验证我方HTTP Adapter、降级和数据流，不把它记录成真实模型Provider验收。
- Redis：DB 14产生12个测试键，类型包含hash/list/string；TTL全部为正，键名不含原始agent/session；验收后精确删除12个，残留0。
- PostgreSQL：复用远程开发库，追加配置与审计；绑定ID 2最终恢复到验收前配置ID 3并保持`ENABLED`，没有删除远程记录。
- 进程：18581、18701、18704按命令行和PID校验后停止；既有8581/PID 7940未停止。

### 8. 提交与遗留风险

提交：

- GenB测试台：`885af5e`（`feat: add core component test bench`）。
- GenB动态配置和绑定重配置：`3c51ada`（`feat: publish component runtime config`）。
- Control/Runtime短期记忆完成：`f152693`（`feat: complete short term memory runtime`）。

遗留风险：

1. Runtime Direct Provider代码和离线合同已存在，但本轮没有可用的正式Provider凭证，因此不能声称真实模型质量、费用、配额和数据保留门禁已经关闭。
2. 指标当前为进程内Prometheus文本注册表；多副本聚合、OTLP Collector、告警规则和容量压测属于M7生产硬化。
3. 配置版本按ID短缓存；主动失效通知尚未实现，当前依赖不可变版本和缓存过期收敛。
4. Short-term Memory一期已经达到M4功能出口，下一Iteration进入Long-term Memory结构化事实、提取Worker、PostgreSQL留存和删除闭环；完整RAG仍属于M13。
