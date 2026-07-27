# 文档索引

## 项目

- `DOC_STATUS.md`：文档可信度、来源和使用规则。
- `TASK_ENTRYPOINTS.md`：常见任务入口卡片。
- `PROJECT_STRUCTURE.md`：项目结构。
- `PROJECT_TERMS.md`：术语表。

## 架构

- `architecture/GENB_ARCHITECTURE.md`：总体架构。
- `architecture/ER_RELATIONSHIP.md`：核心 ER 关系。

## 设计

- `design/CLIENT_UI_DESIGN.md`：客户端 UI 设计记录。
- `design/GENESIS_GENC_UNIFIED_AUTHORIZATION_DESIGN.md`：Genesis 统一管理 GenC 用户、平台角色和菜单权限的详细设计。
- `design/GENB_CORE_MEMORY_COMPONENTS_DETAILED_DESIGN.md`：五大系统与14个核心组件总体设计和全量验收，并细化一期长短记忆、最小Inference Engine的Interface、数据、安全、测试、部署与回滚。

## 开发

- `development/DEVELOPMENT_GUIDE.md`：开发说明。
- `development/CORE_COMPONENT_PLATFORM_DEVELOPMENT_GUIDE.md`：整个核心组件平台开发总入口，覆盖GenB控制面、五大系统/14个组件、智能体接入、自建Inference Engine、公共契约、身份、测试、发布和全量DoD。
- `development/RUNTIME_SYSTEM_INFERENCE_ENGINE_IMPLEMENTATION_GUIDE.md`：Runtime System最小Inference Engine一期专项，覆盖统一模型Interface、Direct/Alaya/Fake Adapter、结构化输出、流式、Embedding、身份、凭证、测试、部署和DoD。
- `development/CONTROL_SYSTEM_MEMORY_IMPLEMENTATION_GUIDE.md`：平台总纲下的Control System长短记忆一期专项，覆盖仓库、Module/Interface、Actor Token、Runtime Inference Adapter、迁移、Redis、提取Worker、前后端、测试、部署和回滚。
- `development/BACKEND_API.md`：后端 API 分组。
- `development/API_CONTRACTS.md`：接口契约、请求响应和 DTO。
- `development/DATABASE_SCHEMA.md`：数据库概要。
- `development/DATABASE_FIELDS.md`：数据库字段明细。
- `development/BACKEND_DATABASE_I18N_IMPLEMENTATION.md`：后端与数据库多语言实现说明、返回字段和前端接入规则。
- `development/CLIENT_GENESIS_I18N_IMPLEMENTATION.md`：业务客户端与 Genesis 门户的语言状态、按钮、请求头和验证说明。

## 安全

- `security/PERMISSION_MATRIX.md`：页面、接口和角色权限矩阵。

## 部署

- `deployment/DEPLOYMENT_GUIDE.md`：部署说明。
- `deployment/GENC_GENO_PRODUCTION_URLS.md`：GenC、GenO 正式访问入口及 Genesis 部署 callback 配置。

## 修改

- `changes/README.md`：修改文档目录说明。
- `changes/20260709-CHANGE-temporary-freeze-date-boundary.md`：临时冻结约束日期边界修正。

## 运维

- `operation/README.md`：运维目录说明。
- `operation/CORE_MEMORY_TESTBENCH_AND_TEST_AGENT_GUIDE.md`：长短期记忆独立测试台与测试智能体详细操作、启动、凭证、隔离、验收和排障手册。

## 培训

- `training/core-memory-testing/lessons/0001-core-memory-testbench-and-agent.html`：分清常驻服务、独立测试台和 CLI 测试智能体，并完成第一个短期记忆闭环。
- `training/core-memory-testing/reference/core-memory-testing-cheatsheet.html`：核心记忆测试现场快速参考。

## 需求

- `requirements/README.md`：需求目录说明。
- `requirements/CORE_COMPONENT_STRUCTURE_PLANNING_SHORT_TERM_CONFIRMATION.md`：五大系统/14组件总体结构、规划与推理引擎及短期记忆/工作台的功能边界和一期效果待确认清单。
- `requirements/CLIENT_I18N_COPY_MAP.md`：Gen-B 客户端前端固定中文文案和英文对照表。
- `requirements/BACKEND_DATABASE_I18N_PLAN.md`：Gen-B 英文版后端返回、数据库动态内容、messageKey 和翻译表改造计划。

## 集成

- `integration/GENESIS_UNIFIED_LOGIN_CHAIN_EXPLAINED.md`：面向开发和非开发人员的 Genesis、Gen-B、Gen-C、Gen-O 统一登录全链路说明。
- `integration/GENESIS_PORTAL_LOGIN_INTEGRATION.md`：Genesis 统一门户登录与 Gen-C/Gen-O 接入说明。
- `integration/GENESIS_GENC_GENO_INTEGRATION_GUIDE.md`：Gen-C / Gen-O 接入 Genesis 统一门户的落地流程、用户映射、授权和 SSO ticket 说明。
- `integration/GENESIS_GENO_SSO_TICKET_INTEGRATION.md`：Gen-O 已有登录体系时，通过 SSO Ticket 接入 Genesis 的完整方案。
- `integration/GENESIS_GENC_SSO_TICKET_INTEGRATION.md`：Gen-C 通过一次性 Ticket、自动建用户和服务端数据隔离接入 Genesis 的实现说明。
