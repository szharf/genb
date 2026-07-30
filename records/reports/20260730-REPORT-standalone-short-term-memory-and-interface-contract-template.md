# 独立短期记忆与核心组件接口契约模板开发报告

> 日期：2026-07-30
> 任务计划：`records/plans/20260730-PLAN-standalone-short-term-memory-and-component-contract-template.md`
> 结论：独立开发和验收完成；未建立GenB/智能体到新服务的调用链，未部署服务器

## 1. 背景

原GenB控制面可以登记组件实现地址、配置和智能体绑定，但不能描述“一个逻辑组件服务具体提供哪些接口”。本次在固定14个组件和服务实现之间新增接口契约层，并用短期记忆组件完成首个可运行样例。

架构口径按用户确认调整为：一组件一项逻辑服务；一个逻辑服务可以有多个接口；相关组件服务可以同属一个系统项目、仓库或部署进程，不要求一组件一系统。

## 2. 完成内容

### 2.1 独立短期记忆服务

新增 `short-term-memory-service`：

- 5个稳定业务 `operationId`。
- `tenant + agent + user + task` 四维隔离。
- `taskId` 跨 `sessionId` 恢复工作台和消息。
- 任务工作台保存、查询和删除。
- 回合幂等提交与冲突409。
- 60秒至30天TTL。
- 对话和工作台嵌套字段持久化前脱敏。
- In-memory Adapter用于测试和最小演示。
- Redis Adapter以单任务原子JSON文档持久化，SHA-256范围键，WATCH/MULTI并发更新。
- Redis不可用时ready返回503，不静默降级。

### 2.2 GenB后端

新增 `component_interface_contracts` 控制面表和契约Module：

- OpenAPI 3.0/3.1 JSON正文。
- OpenAPI 3.0/3.1 YAML正文。
- 上传文件来源记录。
- 页面手工定义多个HTTP接口并生成OpenAPI 3.1。
- 1MB文档、200操作、唯一operationId、路径和responses校验。
- SHA-256契约摘要。
- DRAFT→PUBLISHED不可变发布流程。
- 创建和发布审计。
- 某组件一旦存在契约，注册实现必须选择该组件已发布版本。
- 历史上尚无契约的组件保持兼容。
- JPA逻辑关联不创建物理外键。

新增管理接口：

```text
POST /api/v1/core-components/{componentCode}/contracts
GET  /api/v1/core-components/{componentCode}/contracts
POST /api/v1/core-components/{componentCode}/contracts/{contractId}:publish
```

### 2.3 GenB管理端

组件详情默认页签调整为“接口契约”，新增：

- 契约列表。
- “新建契约”对话框。
- 手工填写、粘贴文档、上传文件三种录入方式。
- JSON/YAML自动识别和文件内容预览。
- 手工接口组件专属默认路径和operationId。
- 多接口新增和删除。
- 接口定义抽屉。
- 草稿发布确认。
- 注册实现时的已发布版本下拉框。
- 完整中英文文案。

同时修复生产语言mode下开发服务缺少 `.env.development` 时，默认API地址错误落到 `/api/core-components` 的问题；现在开发默认统一为 `/api/v1`。

## 3. 数据表

本次只新增1张实际表：

```text
component_interface_contracts
```

原核心组件控制面7张表加本表后共8张。接口操作不重复建表，以规范化OpenAPI JSON为唯一真源。

设计上 `component_id` 逻辑关联 `core_components.id`；实际JPA和Schema测试都禁止物理外键。表保留主键和 `(component_id, contract_version)` 唯一约束，唯一约束不是外键。

### 3.1 远程数据库事实记录

浏览器验收第一次尝试启动隔离后端时，`spring-boot:run` 虽激活了test profile，但未包含 `src/test/resources`，因此仍读取主配置并短暂连接远程开发PostgreSQL。Hibernate执行了：

- 创建 `bank_agent_db.component_interface_contracts`。
- 创建 `(component_id, contract_version)` 唯一约束。

应用随后因Actor Token测试密钥配置缺失而在完成启动前退出。本次没有执行删除、清表或契约数据插入。后续验收已改为显式加入test classpath，使用H2，不再写远程库。该事实保留在报告中，不隐瞒环境副作用。

## 4. 自动化测试

| 范围 | 结果 |
|---|---|
| 短期记忆HTTP、Service与真实Redis | 8项通过 |
| 前端契约纯逻辑 | 4项通过 |
| GenB后端全量 | 122项通过，0失败/0错误/0跳过（含契约控制面与无物理外键Schema） |
| 中文生产构建 | 通过 |
| 英文生产构建 | 通过 |

覆盖行为：跨会话恢复、身份隔离、删除、消息与工作台脱敏、幂等重放/冲突、TTL、OpenAPI operationId、JSON/YAML/手工契约、发布、实现版本门禁和无物理外键。

## 5. 浏览器真实验收

验收使用独立端口：前端19000、H2后端18581，不替换原8581/9000/9100服务。

逐点击完成：

1. 进入“智能体中心→核心组件→短期记忆”。
2. 确认手工模式默认POST、组件路径、operationId和空对象Schema。
3. 通过粘贴JSON创建含5个接口的契约。
4. 查看抽屉确认5个operationId。
5. 发布契约。
6. 打开“注册实现”，确认只能选择已发布版本及5接口摘要。
7. 取消注册，不填写服务地址。
8. 通过上传YAML读取样例文件，自动识别YAML并创建5接口草稿。
9. 浏览器控制台无error/warn。

证据截图：`records/reports/assets/20260730-contract-version-selection.png`。

## 6. 暂不连通证明

本次没有：

- 在远程或H2验收数据中保存新短期记忆真实服务实现。
- 为新实现创建配置。
- 为智能体创建绑定。
- 修改现有测试台使其访问18705。
- 修改测试智能体使其访问18705。
- 接入服务凭证或Actor Token。
- 部署服务器。

新服务从三个身份Header接收范围只用于本地独立测试。正式连通时必须由完成服务凭证、智能体ID和绑定校验的GenB运行入口注入，不能信任公网调用者自填。

## 7. 交付文档

- 详细任务计划：`records/plans/20260730-PLAN-standalone-short-term-memory-and-component-contract-template.md`
- 零基础操作手册：`docs/operation/SHORT_TERM_MEMORY_CONTRACT_REGISTRATION_AND_STANDALONE_TEST_GUIDE.md`
- OpenAPI样例：`docs/samples/short-term-memory-contract-v1.yaml`
- 服务说明：`short-term-memory-service/README.md`

## 8. 后续迭代

下一迭代若获授权，应按以下顺序联通：

```text
注册真实服务实现
→ 创建并发布配置
→ 创建智能体绑定
→ GenB运行入口校验长期服务凭证、agentId和绑定
→ 生成/校验Actor身份
→ 注入可信tenant/agent/user/task范围
→ 调用短期记忆服务
→ 增加测试台和测试智能体端到端验收
```

本轮没有提前实现这条链路，避免把契约模板验收与运行鉴权、路由、重试、审计混成一次不可控变更。
