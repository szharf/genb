# Gen-B 项目索引

更新时间：2026-09-04

这是 `D:\code\opencode\genb` 的项目级索引。目标是让人和 AI 在大项目中快速定位上下文，减少误改、重复搜索和 token 消耗。

## 快速入口

| 文档 | 用途 |
|---|---|
| `AGENTS.md` | AI 协作入口、任务读取规则、当前硬性约束。 |
| `CURRENT_TASKS.md` | 当前任务看板，记录目标、步骤、状态、验证和下一步。 |
| `CONTEXT.md` | GenB 核心组件领域统一术语：核心系统、核心组件、运行时、绑定、记忆和服务凭证。 |
| `docs/INDEX.md` | 文档目录索引。 |
| `docs/DOC_STATUS.md` | 文档可信度、来源、使用方式和必须代码复核的场景。 |
| `docs/TASK_ENTRYPOINTS.md` | 常见需求入口卡片：按任务类型列出必读文档、定向代码和验证方式。 |
| `PROJECT_OVERVIEW.md` | 五个核心项目的定位、调用关系和非核心目录说明。 |
| `ROADMAP.md` | 项目路线图。 |
| `CHANGELOG.md` | 项目级变更记录。 |
| `docs/PROJECT_STRUCTURE.md` | 根目录、核心项目、产物目录、历史目录的结构说明。 |
| `docs/architecture/GENB_ARCHITECTURE.md` | Gen-B 整体架构、前后端、Runtime/CLI、数据库和部署关系。 |
| `docs/architecture/RUNTIME_CLI_ARCHITECTURE.md` | Runtime/CLI 架构和目标链路说明。 |
| `docs/architecture/ER_RELATIONSHIP.md` | 用户、角色、权限、智能体、授权、申请、部署、监控和审计 ER 关系。 |
| `docs/design/GENB_PRODUCT_DESIGN.md` | Gen-B 产品、角色、流程、页面和状态设计。 |
| `docs/design/RUNTIME_CLI_DESIGN.md` | Runtime/CLI 执行链路、安全、Memory、Policy、Workflow 设计。 |
| `docs/design/CLIENT_PAGE_DESIGN.md` | 客户端路由、页面职责、数据来源、状态和组件边界。 |
| `docs/design/CONSOLE_PAGE_DESIGN.md` | 管理端路由、模块职责、接口和修改约束。 |
| `docs/design/GENESIS_GENC_UNIFIED_AUTHORIZATION_DESIGN.md` | Genesis 集中管理 GenC 平台角色与权限、GenC 菜单路由和后端执行的详细设计。 |
| `docs/design/GENB_CORE_MEMORY_COMPONENTS_DETAILED_DESIGN.md` | 五大系统与14个组件总体设计、全量验收，以及一期长短记忆和最小Inference Engine的Interface、数据、权限、测试和部署细化。 |
| `docs/PROJECT_TERMS.md` | 项目术语、业务分类、状态字段和权限术语。 |
| `docs/changes/README.md` | 变更文档目录，记录长期有效的变更说明组织方式。 |
| `docs/changes/20260709-CHANGE-temporary-freeze-date-boundary.md` | 临时冻结约束必须写明具体起止日期的规则修正。 |
| `docs/development/BACKEND_API.md` | 后端 Controller 和 API 分组文档。 |
| `docs/development/API_CONTRACTS.md` | 后端 API 契约、请求/响应结构和关键 DTO。 |
| `docs/development/CORE_COMPONENT_PLATFORM_DEVELOPMENT_GUIDE.md` | 核心组件平台全栈开发总纲：GenB管理控制面、五大系统/14组件执行面、智能体接入编排、自建Inference Engine、公共契约、测试和全量交付。 |
| `docs/development/PLANNING_REASONING_DYNAMIC_SKILL_IMPLEMENTATION.md` | 规划与推理动态需求提示词、任务草稿、受控检索、模型输出规范化、Skill生成与客户页面实现。 |
| `docs/development/RUNTIME_SYSTEM_INFERENCE_ENGINE_IMPLEMENTATION_GUIDE.md` | Runtime System最小Inference Engine一期专项：统一模型Interface、Direct/Alaya/Fake Adapter、身份、凭证、路由、结构化输出、流式、Embedding、测试和部署。 |
| `docs/development/CONTROL_SYSTEM_MEMORY_IMPLEMENTATION_GUIDE.md` | Control System长短记忆一期专项：代码架构、身份、数据、Runtime Inference Adapter、测试、部署和可复用系统模板。 |
| `docs/operation/CORE_MEMORY_TESTBENCH_AND_TEST_AGENT_GUIDE.md` | 长短期记忆独立测试台与测试智能体逐点击操作手册，说明服务启动、服务凭证、A/B 隔离、完整矩阵、证据与排障。 |
| `docs/operation/SHORT_TERM_MEMORY_CONTRACT_REGISTRATION_AND_STANDALONE_TEST_GUIDE.md` | 新版接口契约模板的短期记忆上传/粘贴/手工注册、发布和独立Swagger逐点击测试，明确暂不连通。 |
| `docs/operation/PLANNING_REASONING_GENB_AND_TEST_AGENT_GUIDE.md` | 规划与推理引擎的GenB双模式测试台、专用测试智能体、四种操作、启动和排障逐点击手册。 |
| `docs/training/core-memory-testing/lessons/0001-core-memory-testbench-and-agent.html` | 面向非开发人员的浏览器教学页：分清常驻服务与按命令运行的测试智能体。 |
| `docs/development/DATABASE_SCHEMA.md` | 后端 Entity、核心表和数据关系文档。 |
| `docs/development/DATABASE_FIELDS.md` | 数据库核心字段明细。 |
| `docs/development/BACKEND_DATABASE_I18N_IMPLEMENTATION.md` | 后端与数据库多语言实现说明、返回字段和前端接入规则。 |
| `docs/development/CLIENT_GENESIS_I18N_IMPLEMENTATION.md` | Gen-B 客户端与 Genesis 门户的中英文切换、共享状态和请求语言头说明。 |
| `docs/security/PERMISSION_MATRIX.md` | 客户端、管理端和 API 权限矩阵。 |
| `docs/requirements/CLIENT_I18N_COPY_MAP.md` | Gen-B 客户端前端固定中文文案和英文对照表。 |
| `docs/requirements/CORE_COMPONENT_STRUCTURE_PLANNING_SHORT_TERM_CONFIRMATION.md` | 五大系统/14组件总体结构，以及规划与推理引擎、短期记忆/工作台的功能边界和一期效果待确认清单。 |
| `docs/requirements/BACKEND_DATABASE_I18N_PLAN.md` | Gen-B 英文版后端返回、数据库动态内容、messageKey 和翻译表改造计划。 |
| `docs/integration/GENESIS_PORTAL_LOGIN_INTEGRATION.md` | Genesis 统一门户登录、用户同步、平台授权和 Gen-C/Gen-O 接入说明。 |
| `docs/integration/GENESIS_UNIFIED_LOGIN_CHAIN_EXPLAINED.md` | 面向开发和非开发人员的三平台统一登录流程、差异、接口、配置和排查说明。 |
| `docs/integration/GENESIS_GENC_GENO_INTEGRATION_GUIDE.md` | Gen-C/Gen-O 接入 Genesis 的入口配置、用户映射、授权和 SSO ticket 指南。 |
| `docs/integration/GENESIS_GENO_SSO_TICKET_INTEGRATION.md` | Gen-O 已有登录体系时，通过 SSO Ticket 接入 Genesis 的完整方案。 |
| `docs/integration/GENESIS_GENC_SSO_TICKET_INTEGRATION.md` | Gen-C 一次性 Ticket、首次自动建用户、Cookie 登录态和用户数据隔离说明。 |
| `RUNTIME_CLI_REFACTOR_PLAN.md` | bank-agent-runtime / bank-agent-cli 的详细改造计划。 |
| `context/code-statistics.md` | 核心项目代码量、文档量和文件量统计。 |
| `records/README.md` | 计划、报告、Bug、部署、决策等历史记录入口。 |
| `records/RECORDS_INDEX.md` | 历史记录反向索引，按主题查计划、报告、Bug、部署和决策。 |
| `records/templates/PLAN_TEMPLATE.md` | 标准任务计划模板：基础结构及复杂架构任务的arc42/KEP/MADR扩展，覆盖失败基线、决策、运行时、Interface、安全、测试、Gate与回滚。 |
| `records/reports/20260806-REPORT-three-core-component-service-convergence-m5.md` | 短期、长期会话记忆、规划与推理独立服务收敛的Gate F完成证据。 |
| `CLEANUP_GUIDE.md` | 当前目录下可删除、谨慎删除、不可删除内容说明。 |

## 当前工作树

| 层级 | 当前结论 | 唯一入口 |
|---|---|---|
| 当前生产任务 | GenB 后端已合并同事最新 MCP 代码并部署；核心组件目录路由恢复，智能体运行中优先排序生效。未部署核心组件模型。 | `records/deployments/20260904-部署-合并同事代码并更新GenB后端.md` |
| 当前执行结果 | 后端、必要 SQL 和 GenB 专用本机 Redis 已上线；管理端核心组件模型、统一数据面网关和其他项目服务未部署。 | `records/deployments/20260904-部署-合并同事代码并更新GenB后端.md` |
| 已完成本地实现 | 统一数据面网关 M0-M5、合同、GenB 控制面、管理端、18714 与三组件本地 Gate A-F 已完成。 | `records/reports/20260813-REPORT-unified-data-plane-gateway-m5.md` |
| 生产运行状态 | 47 根分区当前约 53%，GenB `8581` 健康 `UP`；`genb-redis` 仅绑定本机，生产 JAR 和数据库备份可用于回滚。 | `records/deployments/20260904-部署-合并同事代码并更新GenB后端.md` |
| 同事源码交付 | 模块、启动、配置、数据库与打包排除项说明。 | `gen-b/项目说明.md` |
| 初始化数据库 | GenB 当前 Entity 对应的 PostgreSQL 建表与索引脚本。 | `gen-b/创建所需表.sql` |

阅读顺序：`CURRENT_TASKS.md` 当前任务 → 对应计划 → 对应报告/部署记录 → 定向代码。历史任务只通过 `records/RECORDS_INDEX.md` 反查。

## 核心项目

| 项目 | 路径 | 说明 |
|---|---|---|
| 智能体 CLI | `bank-agent-project/bank-agent-cli` | 生成标准智能体项目的脚手架。 |
| 智能体 Runtime/SDK | `bank-agent-project/bank-agent-runtime` | 智能体运行时底座和 SDK。 |
| Runtime System服务 | `runtime-system-service` | 核心组件平台模型执行面；提供统一推理、结构化输出、路由与凭证校验，18714通过它完成真实模型回答。 |
| Control System服务 | `control-system-service` | Control System接入与组合层；通过GenB签发的Actor Token/组件会话连接独立短期、长期与规划服务，不作为组件公共真源。 |
| 独立短期记忆服务 | `short-term-memory-service` | `SHORT_TERM_MEMORY`唯一公共Implementation真源；Interface 1.1.0，提供四维隔离、TTL、幂等、脱敏及内存/Redis Adapter。 |
| 独立长期记忆服务 | `long-term-memory-service` | `LONG_TERM_MEMORY`唯一公共Implementation真源；Interface 1.0.0，当前实现Conversation Memory，Knowledge Base通过内部Adapter由同事接入。 |
| 规划与推理引擎服务 | `planning-reasoning-service` | 固定组件`PLANNING_REASONING`的一期独立逻辑服务；提供需求澄清、简单/复杂Skill生成、MCP声明、校验、版本修订、GenB身份和PostgreSQL持久化。 |
| Control System测试智能体 | `control-system-test-agent` | 18714客户唯一入口；通过一次性授权码、Redis服务端会话和HttpOnly Cookie接入统一门户，以自然语言验收短期、长期和规划能力。 |
| 统一数据面网关 | `genb-data-plane-gateway` | 智能体访问与核心能力调用的统一数据面，提供身份交换、会话、路由、Adapter、缓存失效和审计；当前仅完成本地实现与验收，未生产部署。 |
| Gen-B 后端 | `gen-b/gen-b-backend` | 登录、用户、角色、权限、智能体、授权申请、审批、状态、部署管理，以及核心组件目录、配置、绑定、治理、服务凭证和短时组件会话控制面（Iteration 5）。 |
| Gen-B 客户端 | `gen-b/gen-b-client` | 业务用户门户：我的智能体、智能体市场、我的申请、个人中心。 |
| Gen-B 管理端 | `gen-b/gen-b-console` | 管理端/运维管控前端。 |

## 常见任务导航

常见需求统一从 `docs/TASK_ENTRYPOINTS.md` 进入。它按任务类型列出：

- 必读文档。
- 定向代码路径。
- 验证方式。
- 部署和服务器操作风险提醒。

默认流程：

```text
AGENTS.md
→ PROJECT_INDEX.md
→ docs/TASK_ENTRYPOINTS.md
→ 相关专题文档
→ 定向代码
→ 验证
→ records 记录
```

## 文档命名规范

| 类型 | 目录 | 命名 |
|---|---|---|
| 计划 | `records/plans/` | `YYYYMMDD-PLAN-主题.md` |
| 报告 | `records/reports/` | `YYYYMMDD-REPORT-主题.md` |
| Bug | `records/bugs/` | `YYYYMMDD-BUG-主题.md` |
| 决策 | `records/decisions/` | `YYYYMMDD-ADR-主题.md` |
| 部署 | `records/deployments/` | `YYYYMMDD-DEPLOY-主题.md` |
| 用户提问 | `records/asks/` | `YYYYMMDD-ASK-主题.md` |

## 维护原则

- 文档服务于定位和复核，不追求形式复杂。
- 每次较大修改至少留下计划或报告。
- Bug 修复要记录现象、原因、改动、验证。
- 部署要记录服务器、路径、包名、命令、回滚点。
- 发现现有文档过期时，优先补充索引或标注状态，不批量重写。

## 知识库维护节奏

| 场景 | 必做记录 |
|---|---|
| 新需求 | `CURRENT_TASKS.md` + `docs/requirements/` |
| 设计变化 | `docs/design/` 或 `docs/architecture/` |
| 代码改造 | `records/plans/` + `records/reports/` |
| Bug 修复 | `records/bugs/` + 测试结果 |
| 部署 | `records/deployments/` |
| 长期规则变化 | `docs/changes/` |
| 阶段总结 | `CHANGELOG.md` + `records/reports/` |

新增记录后，同步更新 `records/RECORDS_INDEX.md`。
