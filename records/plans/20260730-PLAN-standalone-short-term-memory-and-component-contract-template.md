# 独立短期记忆服务与核心组件接口契约模板详细开发计划

> 日期：2026-07-30
> 状态：已实施并完成独立验收
> 实施范围：独立短期记忆服务、GenB核心组件接口契约管理、管理端页面、独立测试和零基础操作手册
> 明确不做：短期记忆服务与GenB真实运行时连通、智能体绑定调用、SDK、MCP Adapter、服务器部署

## 1. 背景

当前GenB已经具备固定五大系统/14个核心组件目录、组件实现注册、配置版本、智能体绑定、服务凭证和测试台。现有组件实现注册只记录：

- 实现编码。
- 负责人。
- 运行类型。
- Interface版本。
- `baseUrl`。
- `healthUrl`。
- 状态。

这个模型可以说明“服务部署在哪里”，但不能说明“一个服务提供哪些接口、每个接口如何请求、参数和返回是什么”。短期记忆与长期记忆现有测试路径由GenB后端写死，因此不能直接复用于规划与推理引擎或其他组件。

本任务将模型调整为：

```text
固定核心组件
  → 稳定接口契约版本
      → 多个HTTP操作
  → 一个或多个服务实现
      → 声明支持某个已发布契约版本
```

同时新建一个独立短期记忆服务作为该模板的第一份标准样例。短期记忆服务生成标准OpenAPI文档；GenB支持文档上传、正文粘贴和逐接口手工填写三种录入方式，但本轮不让GenB调用该服务。

## 2. 与现有架构决策的关系

现有ADR默认建议“五个系统项目承载14个内部组件Module”。本次进一步确认：14个组件分别是14个逻辑服务，但相关服务可以由同一个系统项目、代码仓库或部署进程共同承载。

本任务采用以下安全解释：

1. 14个组件在产品、契约、权限、版本和注册层都是独立逻辑服务。
2. “一组件一服务”不等于“一组件一系统/项目/仓库/进程”。
3. 相关组件服务可以共同位于一个核心系统项目中，并共享一次部署。
4. 一个系统项目承载多个组件时，每个组件仍使用独立`componentCode`、Interface版本、配置和绑定。
5. 本轮把短期记忆做成可独立启动的参考服务，但该形态不是其他13个组件必须复制的物理部署要求。

## 3. 本轮目标

### 3.1 独立短期记忆服务

完成一个不依赖旧Runtime SDK、不依赖Control System进程的HTTP服务，提供：

- 跨会话任务工作台。
- 多轮消息提交。
- 上下文准备。
- 任务查询。
- 任务删除。
- TTL。
- 幂等。
- 敏感信息持久化前脱敏。
- 四维身份隔离。
- 健康检查。
- OpenAPI 3.1接口文档。

### 3.2 GenB核心组件模块

在现有固定组件目录与服务实现之间增加“接口契约”层，提供：

- HTTP契约草稿创建，支持OpenAPI 3.0/3.1 JSON/YAML和手工接口定义。
- 文档结构校验。
- 多接口解析。
- 契约发布。
- 契约版本列表。
- 接口详情查看。
- 契约摘要值校验。
- 服务实现声明支持契约版本。
- 操作审计。

### 3.3 管理端页面

管理员可以在核心组件详情页完成：

1. 新建接口契约。
2. 选择上传文件、粘贴正文或手工填写。
3. 查看解析出的接口列表。
4. 查看请求参数、请求体和响应定义。
5. 发布契约。
6. 注册支持该契约的服务实现。

### 3.4 操作手册

形成一份完全没有使用过系统的管理员也能执行的手册，包含：

- 从哪里进入。
- 点击哪个菜单。
- 每个按钮的作用。
- 每个字段输入什么。
- 示例值。
- 正确结果。
- 常见错误及处理方式。
- 为什么必须按此顺序操作。

## 4. 明确范围外

以下内容不在本轮实现：

- GenB根据契约动态代理短期记忆调用。
- 智能体真实申请短期记忆组件会话并调用新服务。
- 将当前Control System数据迁移到新服务。
- 新服务连接GenB服务凭证内省和Actor Token。
- SDK代码生成。
- MCP Server或MCP Adapter。
- OpenAPI远程URL自动抓取。
- 规划与推理引擎实现。
- 服务器部署或生产数据迁移。

“暂不连通”的验收含义：

- 两个应用可以各自启动。
- 两边自动化测试分别通过。
- 管理员可以手工把OpenAPI文档录入GenB。
- GenB不会向短期记忆服务发送业务请求或健康请求。
- 新短期记忆服务也不会调用GenB。

## 5. 总体结构

```text
┌──────────────────────────────────────────────┐
│ GenB管理控制面                               │
│                                              │
│ 固定组件 SHORT_TERM_MEMORY                   │
│   ├─ Interface Contract 1.0.0                │
│   │   ├─ prepareShortTermContext             │
│   │   ├─ commitShortTermTurn                 │
│   │   ├─ saveTaskWorkbench                   │
│   │   ├─ getTaskWorkbench                    │
│   │   └─ deleteTaskWorkbench                 │
│   └─ Component Implementation                │
│       ├─ baseUrl                             │
│       ├─ healthUrl                           │
│       └─ supportedContractVersion            │
└──────────────────────────────────────────────┘

                 本轮不建立调用链

┌──────────────────────────────────────────────┐
│ 独立Short-term Memory Service                │
│   ├─ HTTP Interface                          │
│   ├─ Task Workbench Module                   │
│   ├─ Conversation Memory Module              │
│   ├─ Redaction Module                        │
│   ├─ In-memory Adapter（测试）                │
│   └─ Redis Adapter（本地/正式运行）           │
└──────────────────────────────────────────────┘
```

## 6. 独立短期记忆服务详细设计

### 6.1 项目位置

```text
D:\code\opencode\genb\short-term-memory-service
```

### 6.2 技术栈

- Python 3.11+。
- FastAPI。
- Pydantic v2。
- Uvicorn。
- Redis作为运行数据存储。
- In-memory Adapter仅用于自动化测试和本地最小演示。

不新增C盘运行时，不安装与项目无关的软件。

### 6.3 身份和隔离

数据唯一范围：

```text
tenantId + agentId + userId + taskId
```

关系：

```text
tenantId
└─ agentId
   └─ userId
      └─ taskId
         ├─ sessionId-1
         ├─ sessionId-2
         └─ sessionId-3
```

- `taskId`用于跨天、跨周、跨多次聊天恢复同一业务任务。
- `sessionId`只标识一次聊天过程。
- 一个`taskId`可以包含多个`sessionId`。
- 不允许只凭`taskId`跨用户或跨智能体读取。

由于本轮不连接GenB，测试/本地模式从以下Header接收身份：

- `X-Tenant-Id`。
- `X-Agent-Id`。
- `X-User-Id`。

这些Header不是生产认证方案。未来连通时应由服务凭证与Actor Token解析得到，生产模式禁止信任调用方直接提交的身份Header。

### 6.4 HTTP Interface

#### 6.4.1 保存任务工作台

```text
PUT /api/v1/short-term-memory/tasks/{taskId}
operationId: saveTaskWorkbench
```

请求体：

```json
{
  "status": "WAITING_MATERIAL",
  "instructions": ["优先核对营业执照"],
  "progress": "已完成基础信息检查",
  "pendingMaterials": ["近三个月流水"],
  "toolResults": [
    {"tool": "company-search", "summary": "企业状态正常"}
  ],
  "resumeCheckpoint": "等待用户补充流水",
  "expiresInSeconds": 86400
}
```

#### 6.4.2 查询任务工作台

```text
GET /api/v1/short-term-memory/tasks/{taskId}
operationId: getTaskWorkbench
```

不存在或不属于当前身份范围时返回404，不泄露其他身份是否存在同名任务。

#### 6.4.3 删除任务工作台

```text
DELETE /api/v1/short-term-memory/tasks/{taskId}
operationId: deleteTaskWorkbench
```

删除工作台、消息和幂等记录。重复删除保持安全。

#### 6.4.4 提交一轮对话

```text
POST /api/v1/short-term-memory/turns:commit
operationId: commitShortTermTurn
Idempotency-Key: 必填
```

请求体：

```json
{
  "taskId": "credit-review-001",
  "sessionId": "chat-001",
  "turnId": "turn-001",
  "userMessage": "请检查企业基本资料",
  "assistantMessage": "基础资料已经检查完成",
  "occurredAt": "2026-07-30T10:00:00Z"
}
```

同一幂等键和相同正文重复提交时返回原结果；同一幂等键对应不同正文时返回409。

#### 6.4.5 准备上下文

```text
POST /api/v1/short-term-memory/context:prepare
operationId: prepareShortTermContext
```

请求体：

```json
{
  "taskId": "credit-review-001",
  "sessionId": "chat-002",
  "query": "继续办理",
  "maxMessages": 20
}
```

返回同一任务下允许召回的最近消息和工作台。返回的消息保留原`sessionId`，让智能体知道内容来自哪次聊天。

### 6.5 健康和契约

```text
GET /health/live
GET /health/ready
GET /openapi.json
GET /docs
```

`ready`必须区分In-memory和Redis Adapter。Redis配置存在但不可用时返回非就绪，不静默回退到内存。

### 6.6 Redis数据设计

不创建SQL表。最终采用“一任务一个原子JSON文档”，键中只保存四维范围键的SHA-256摘要：

```text
genb:short-term-memory:v1:task:{scopeAndTaskSha256}
```

要求：

- 工作台、消息和幂等记录位于同一文档并使用同一TTL。
- 更新工作台时刷新允许范围内的TTL。
- 回合提交使用Redis WATCH/MULTI乐观事务保证消息和幂等记录原子更新。
- 删除只删除精确任务键，不扫描或清理其他任务。
- Redis密码只从环境变量读取。

### 6.7 敏感信息

持久化前处理：

- `password`、`passwd`、`pwd`。
- `token`、`access_token`、`refresh_token`。
- 验证码。
- 后续补充的银行卡、证件号规则应经过误伤评审。

正文只保存脱敏结果。日志、错误和审计不得记录原始请求正文、认证Header或Redis密码。

## 7. GenB接口契约模板详细设计

### 7.1 三层模型

#### 固定核心组件

表示固定能力，例如`SHORT_TERM_MEMORY`。不允许管理员随意新增第15个组件。

#### 接口契约

表示组件对调用方承诺的稳定Interface版本。一份契约包含多个HTTP操作。

#### 服务实现

表示某个团队部署的一份实现，只登记实现信息、地址、健康地址和支持的契约版本。

### 7.2 契约录入方式

一期支持三种录入方式：

1. `DOCUMENT_UPLOAD`：上传`.json`、`.yaml`或`.yml`文件。
2. `DOCUMENT_PASTE`：在文本框粘贴OpenAPI JSON或YAML。
3. `MANUAL`：逐接口填写请求方法、路径、参数、请求体、响应和权限。

无论使用哪种方式，GenB最终都生成并保存一份规范化OpenAPI JSON，作为HTTP Interface的内部统一表示。这样接口列表、测试表单、SDK生成和后续MCP Adapter可以复用同一个解析结果。

MCP作为另一类契约协议保留扩展位置；本轮只完成HTTP契约录入和展示，不实现MCP运行时调用。SDK是HTTP调用封装，不作为单独协议或Implementation。

### 7.3 OpenAPI规则

文档模式接受OpenAPI 3.0.x和3.1.x的JSON或YAML：

- 文档必须为JSON对象。
- `openapi`必须为`3.0.x`或`3.1.x`。
- 必须包含`info`。
- 必须包含至少一个`paths`操作。
- 每个操作必须有唯一`operationId`。
- 每个操作必须有`responses`。
- 路径必须以`/`开头。
- 单份文档最大1MB。
- 单份契约最多200个操作。
- 契约保存SHA-256摘要值。

一期不自动下载远程URL，避免SSRF和环境连通问题。

### 7.4 手工接口默认值

管理员选择“手工填写”后，页面自动创建第一条接口并填入：

| 字段 | 默认值 |
|---|---|
| 契约版本 | `v1`（管理员可改为SemVer，例如`1.0.0`） |
| 协议 | `HTTP` |
| 请求方式 | `POST` |
| 接口路径 | `/api/v1/{component-slug}` |
| `operationId` | 根据组件编码生成，例如`invokeShortTermMemory` |
| Content-Type | `application/json` |
| 请求体 | `{"type":"object","properties":{}}` |
| 成功状态码 | `200` |
| 成功响应 | `{"type":"object","properties":{}}` |
| 超时 | `5000ms` |
| 是否幂等 | 否 |
| 认证 | 服务凭证 + Actor Token（仅契约说明，本轮不连通） |

管理员可以新增和删除接口；一份契约至少保留一个接口。复杂参数建议优先使用OpenAPI文件录入。

### 7.5 数据设计

新增一张实际表：

```text
component_interface_contracts
```

字段：

| 字段 | 作用 |
|---|---|
| `id` | 主键 |
| `component_id` | 逻辑关联固定组件，不创建物理外键 |
| `contract_version` | 契约版本 |
| `protocol` | 一期为`HTTP`，预留`MCP` |
| `source_type` | 上传、粘贴或手工填写 |
| `source_format` | JSON、YAML或MANUAL |
| `source_name` | 原始文件名或来源说明 |
| `checksum` | OpenAPI正文SHA-256 |
| `open_api_json` | 不可变契约正文 |
| `change_summary` | 变更说明 |
| `status` | `DRAFT`或`PUBLISHED` |
| `created_by` | 创建人 |
| `published_by` | 发布人 |
| `published_at` | 发布时间 |
| `row_version` | 并发版本 |

接口操作一期从规范化OpenAPI正文解析，不创建重复的操作明细表，避免正文和明细双真源不一致。手工填写的接口在提交前由后端构建为规范化OpenAPI JSON。后续如果需要复杂检索，再增加只读投影表。

设计关系可以表达外键，实际建表不创建物理外键。

### 7.6 管理Interface

#### 创建契约草稿

```text
POST /api/v1/core-components/{componentCode}/contracts
权限：component.configure
```

#### 查询契约版本

```text
GET /api/v1/core-components/{componentCode}/contracts
权限：component.read
```

#### 发布契约

```text
POST /api/v1/core-components/{componentCode}/contracts/{contractId}:publish
权限：component.configure
```

#### 实现注册约束

当某个组件已经存在接口契约后：

- 新实现必须选择一个已发布契约版本。
- 草稿契约不能被实现声明支持。
- 未知契约版本不能注册。
- 历史上没有契约的组件保持兼容，避免一次性破坏现有数据。

### 7.7 生命周期

```text
创建草稿
→ 后端校验OpenAPI
→ 管理员查看接口列表
→ 管理员发布
→ 服务实现选择已发布版本
```

已发布契约不可直接修改。需要变更时创建新`contractVersion`。

## 8. 管理端页面计划

### 8.1 页面位置

```text
智能体中心
└─ 核心组件
   └─ 短期记忆
      └─ 详情页
```

### 8.2 页签结构

详情页调整为：

1. 接口契约。
2. 服务实现。
3. 配置版本。
4. 智能体绑定。
5. 管理审计。
6. 独立测试台（仅记忆组件显示）。

本轮“独立测试台”仍保持现状，不接新短期记忆服务。

### 8.3 Vue组件边界

| 组件 | 单一职责 | 输入 | 输出事件 |
|---|---|---|---|
| `CoreComponentContractTable.vue` | 展示契约版本和操作按钮 | contracts、busy | view、publish、create |
| `CoreComponentContractDialog.vue` | 选择录入方式并录入版本、来源、说明和契约 | visible、busy | submit、close |
| `CoreComponentManualOperationEditor.vue` | 手工编辑多个HTTP接口并提供默认值 | operations、componentCode | update、add、copy、remove |
| `CoreComponentOperationDrawer.vue` | 展示参数、请求体、响应和Scope | operation、visible | close |
| `useCoreComponentGovernance.js` | 请求、加载、错误和刷新 | componentCode | actions/state |
| `Detail.vue` | 组合页面，不承载契约业务逻辑 | route | 无 |

使用Composition API、`<script setup>`、props down/events up。派生状态使用`computed`，请求副作用由composable统一管理。

### 8.4 “新建接口契约”对话框

字段：

| 字段 | 控件 | 是否必填 | 示例 |
|---|---|---|---|
| 契约版本 | 输入框 | 是 | `1.0.0` |
| 协议 | 选择框 | 是 | `HTTP`，预留`MCP` |
| 录入方式 | 单选按钮 | 是 | 上传文件、粘贴正文、手工填写 |
| 来源名称 | 输入框 | 是 | `short-term-memory-openapi.json` |
| 变更说明 | 多行输入 | 是 | `短期记忆独立服务首版契约` |
| OpenAPI文档 | 文件上传/JSON或YAML文本框 | 文档模式必填 | OpenAPI 3.0/3.1 |
| 接口定义 | 手工接口编辑器 | 手工模式必填 | 默认生成一条POST接口 |

按钮：

- `取消`：关闭且不保存。
- `校验并创建草稿`：文档模式先解析JSON/YAML，手工模式先校验字段；成功后刷新契约表。

### 8.5 契约列表按钮

- `新建接口契约`：打开对话框。
- `查看接口`：在下方显示该版本所有操作。
- `发布`：只对草稿显示，弹出二次确认。
- 已发布版本不显示编辑按钮。

### 8.6 接口列表

列：

- 请求方法。
- 请求路径。
- `operationId`。
- 功能说明。
- 标签。
- 所需Scope。
- 操作：`查看定义`。

查看定义抽屉展示：

- Path/Query/Header参数。
- Request Body。
- Responses。
- Scope。

JSON只做格式化文本展示，不使用`v-html`。

## 9. TDD与验证计划

### 9.1 短期记忆服务

按纵向切片逐项RED→GREEN：

1. 同一任务跨`sessionId`恢复工作台和消息。
2. 不同用户、智能体、租户不可读取相同`taskId`。
3. 任务可以读取和删除。
4. 敏感值在存储前脱敏。
5. 回合提交幂等重放且冲突返回409。
6. TTL到期后不可读取。
7. Redis Adapter真实集成测试使用独立DB和唯一前缀。
8. OpenAPI包含稳定`operationId`、参数和响应Schema。

### 9.2 GenB后端

1. 管理员可以创建包含多个操作的OpenAPI草稿。
2. 非OpenAPI 3.1、重复`operationId`、缺少响应、超大文档被拒绝。
3. 草稿可以发布，已发布不能重复发布或修改。
4. 普通无权限用户不能创建或发布。
5. 接口列表能返回方法、路径、参数、请求体和响应。
6. 已有契约后，实现只能选择已发布契约版本。
7. 数据库Schema测试确认无物理外键。
8. 既有核心组件控制面测试不回归。

### 9.3 管理端

1. JSON/YAML解析、手工默认值和表单校验纯逻辑测试。
2. 只有草稿显示发布按钮。
3. 接口列表由OpenAPI解析结果驱动。
4. 发布后刷新状态。
5. 中文和英文文案完整。
6. 中英文生产构建通过。

### 9.4 真实页面验收

1. 启动GenB后端和管理端。
2. 登录管理员。
3. 进入短期记忆详情。
4. 使用样例OpenAPI创建契约草稿。
5. 查看5个接口。
6. 展开参数和响应。
7. 发布契约。
8. 打开实现注册，确认只能选择已发布版本。
9. 不填写短期记忆服务地址或不执行调用，证明暂未连通。
10. 保存截图和浏览器控制台错误记录。

## 10. 实施阶段和门禁

### M0：计划确认

- 产物：本计划。
- 门禁：用户确认范围、独立服务解释、OpenAPI方式和暂不连通边界。
- 未通过时不得继续新增功能。

### M1：短期记忆Interface与In-memory纵向切片

- 完成公开HTTP Interface。
- 完成跨会话恢复、隔离、幂等、脱敏和删除测试。
- 导出稳定OpenAPI 3.1。

### M2：Redis Adapter和运行保护

- 增加Redis Adapter。
- TTL和原子幂等。
- 请求大小、超时和健康检查。
- 保留In-memory测试Adapter。

### M3：GenB契约管理后端

- 新增契约实体、Repository、解析Module、Service和Controller。
- 完成草稿、列表、发布和审计。
- 完成实现版本约束。
- 确认无物理外键。

### M4：GenB管理端

- 新增契约页签、对话框、接口列表和定义抽屉。
- 补中英文。
- 完成页面逻辑测试。

### M5：独立验收

- 服务测试。
- GenB后端全量测试。
- 管理端逻辑测试和双语构建。
- 浏览器逐点击验收。
- 明确不做互联调用。

### M6：文档和交付

- 零基础逐点击注册手册。
- 开发报告。
- OpenAPI样例文件。
- 启停说明。
- 索引更新。
- 精确提交，不混入历史生成物。

## 11. 每阶段完成后的汇报内容

每个阶段必须回答：

1. 完成了什么。
2. 修改了哪些真实文件。
3. 新增了哪些接口或按钮。
4. 自动化测试结果。
5. 页面是否实际打开验证。
6. 当前是否已经连通。
7. 下一阶段开始前还有什么风险。

## 12. 风险和控制

| 风险 | 控制方式 |
|---|---|
| 误把14个逻辑服务直接扩成14个生产进程 | 本轮只拆短期记忆试点，不修改其他13个部署形态 |
| OpenAPI正文与接口列表不一致 | 正文作为唯一真源，列表实时解析 |
| 上传恶意或超大文档 | 只接收JSON、最大1MB、最多200操作、严格结构校验 |
| 远程URL引入SSRF | 一期不允许后端主动抓取URL |
| 服务实现声称支持不存在的版本 | 存在契约后只允许选择已发布版本 |
| 短期记忆跨用户泄露 | 所有操作统一使用四维范围键 |
| 密码、Token进入Redis或日志 | 持久化前脱敏，日志禁止正文和认证Header |
| 工作区历史生成物混入提交 | 只精确暂存本任务源文件、测试和文档 |
| 本地正在运行的旧后端锁定`target/classes` | 测试使用独立构建目录，不停止用户已有进程 |

## 13. 回滚策略

- 新短期记忆服务是新增目录，不替换现有Control System。
- GenB新增契约表和页面，不删除现有实现、配置或绑定表。
- 暂不连通，因此回滚不会影响现有智能体调用。
- 页面变更可独立回滚，后端旧接口保持兼容。
- 不执行数据库删除或历史数据迁移。

## 14. 完成检查点

- 独立短期记忆服务完成HTTP、四维隔离、跨会话恢复、TTL、幂等、脱敏、内存与Redis Adapter。
- GenB完成JSON/YAML上传、正文粘贴、手工默认值、解析、草稿、发布、查看、审计和实现版本约束。
- 管理端完成接口契约页签、三种录入方式、接口抽屉、发布与已发布版本下拉框，并补齐中英文。
- H2集成测试确认新增控制面表无物理外键；真实Redis完成跨服务实例恢复测试。
- 浏览器逐点击完成粘贴5接口、YAML上传5接口、查看、发布和实现下拉约束验收，控制台无错误。
- 当前仍未建立GenB、智能体与新短期记忆服务的调用连接，未部署服务器。

## 15. 用户已确认的计划项

1. 一组件一逻辑服务，但相关组件服务可以位于同一个系统项目中，不要求一组件一系统。
2. 契约录入应多元化，支持OpenAPI 3.0/3.1 JSON/YAML和后续协议扩展。
3. 一期同时支持上传、粘贴和带默认值的手工填写。
4. 本轮做到可注册、可发布、可查看，但不让GenB、智能体调用新服务。
