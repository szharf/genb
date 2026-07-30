# 历史记录反向索引

- `records/plans/20260730-PLAN-agent-binding-auth-credential-and-memory-chat.md`：绑定名称、统一退出、未登录路由守卫、测试凭证持久化和短期记忆聊天智能体实施计划。
- `records/reports/20260730-REPORT-agent-binding-auth-credential-and-memory-chat.md`：五项功能实现、双层鉴权、真实两轮短期记忆聊天及浏览器验收报告。
- `records/plans/20260730-PLAN-short-term-memory-runtime-connection-and-dual-testbench.md`：独立短期记忆服务与GenB真实联通、管理员服务直测和智能体绑定测试双路径的详细任务计划。
- `records/reports/20260730-REPORT-short-term-memory-runtime-connection-and-dual-testbench.md`：短期记忆服务真实注册、双模式测试台、可信身份、远程开发数据和端到端验收报告。
- `docs/operation/SHORT_TERM_MEMORY_RUNTIME_CONNECTION_AND_DUAL_TESTBENCH_GUIDE.md`：面向零基础管理员的注册结果检查、服务直测、凭证获取、智能体测试和负向测试逐点击手册。

更新时间：2026-07-30

本文按主题索引 `records/` 下的历史记录，用于快速追溯背景、已做过的验证和历史结论。历史记录可信度低于当前代码，仅作为线索。

## 工程知识库

| 主题 | 文件 | 说明 |
|---|---|---|
| 工程知识库建设计划 | `records/plans/20260708-PLAN-engineering-knowledge-base.md` | 文档体系建设计划。 |
| 工程知识库增强报告 | `records/reports/20260708-REPORT-engineering-knowledge-base.md` | 第一轮知识库增强总结。 |
| 工程知识库补全报告 | `records/reports/20260708-REPORT-knowledge-base-completion.md` | 后端接口概要、数据库概要、页面设计文档补全。 |
| 接口/数据库/权限细化报告 | `records/reports/20260708-REPORT-api-db-permission-detail.md` | API 契约、字段、ER、权限矩阵补充。 |
| Genesis 统一门户第一版 | `records/reports/20260709-REPORT-genesis-portal-v1.md` | Genesis 用户体系、门户页、平台解锁和对接文档实施记录。 |
| Genesis 门户 Logo 与 Gen-C/Gen-O 接入文档 | `records/reports/20260709-REPORT-genesis-portal-logo-and-genco-guide.md` | 门户顶部 logo、标题、横线移除和 Gen-C/Gen-O 接入文档记录。 |
| Gen-B 后端与数据库国际化计划 | `records/reports/20260710-REPORT-backend-database-i18n-plan.md` | 后端返回、数据库动态内容、messageKey 和翻译表计划记录。 |
| Codex 全局语言与安装下载规则 | `records/reports/20260713-REPORT-codex-global-install-download-rules.md` | 全局中文回复、D/E 盘优先和安装下载记录规则设置。 |
| 统一任务报告模板 | `records/reports/20260713-REPORT-standardize-task-report-template.md` | 将新任务报告统一为背景、目标、范围、完成标准、计划、进度、验收和风险八段式结构。 |
| Genesis 与 Gen-O 统一登录实现 | `records/reports/20260713-REPORT-genesis-geno-sso-implementation.md` | Genesis 一次性 ticket、Gen-O JWT exchange、前端 callback、测试和本地提交记录。 |
| Genesis 与 Gen-O 本地联调 | `records/reports/20260713-REPORT-genesis-geno-local-debug.md` | 本地服务启动、admin 映射授权、接口与浏览器端到端验收。 |
| Genesis 用户与平台权限管理 | `records/reports/20260713-REPORT-genesis-access-management.md` | 统一门户用户映射、用户直接授权、角色继承状态及管理端页面。 |
| 本地管理端同源代理 | `records/reports/20260714-REPORT-local-console-proxy.md` | 区分本地 Vite 代理和服务器 Nginx，修复管理端登录后空白。 |
| Genesis 与 Gen-C 统一登录计划 | `records/plans/20260714-PLAN-genesis-genc-sso.md` | Gen-C 一次性登录凭证、本地会话、用户数据隔离、测试和部署边界计划。 |
| Genesis 与 Gen-C 统一授权计划 | `records/plans/20260720-PLAN-genesis-genc-unified-authorization.md` | Genesis 集中配置 GenC 平台角色和权限、GenC 菜单路由与接口执行、逐步验证门禁计划。 |
| GenC 角色权限可配置计划 | `records/plans/20260721-PLAN-genesis-genc-role-permission-management.md` | 在 GenB 统一门户权限页面配置 GenC `ADMIN`、`USER` 权限组合，包含初始化、接口、页面、SSO 和逐步验证方案。 |
| Genesis 门户稳定短 URL 计划 | `records/plans/20260721-PLAN-genesis-portal-stable-short-url.md` | 分离 Vue Router 与静态资源/API 基路径，使 `/portal/login` 加载和登录后保持不变并兼容旧入口。 |
| 个人分支、GenC 权限与备份盘点计划 | `records/plans/20260721-PLAN-personal-branch-genc-permissions-backup-inventory.md` | 三仓库建立 `szharf-dev`，保存当前成果，启动权限开发并只读整理 Codex 备份。 |
| GenB 中英文双版本 Nginx 路由处理计划 | `records/plans/20260722-PLAN-genb-bilingual-nginx-routing.md` | 固定中文 `/genb` 与英文 `/genb-en`，记录英文构建 base、Nginx 路由、验证门禁和回滚顺序。 |
| 核心组件平台详细实施计划 | `records/plans/20260723-PLAN-core-component-platform-implementation.md` | 从公共契约、Inference Engine、GenB控制面、长短记忆到五系统14组件总体验收的里程碑、工作包和当前Iteration 1/2。 |
| 独立短期记忆与组件契约模板计划 | `records/plans/20260730-PLAN-standalone-short-term-memory-and-component-contract-template.md` | 新建独立短期记忆服务，增加GenB OpenAPI 3.1多接口契约管理、管理端页面、独立验收和零基础注册手册；本轮明确暂不互联。 |
| 独立短期记忆与接口契约模板交付 | `records/reports/20260730-REPORT-standalone-short-term-memory-and-interface-contract-template.md` | 完成短期记忆独立服务、Redis Adapter、GenB三种契约录入/发布/查看、实现版本约束、双语页面与真实浏览器验收，并记录暂不互联及远程表创建事实。 |
| Long-term Memory Iteration 13 | `records/reports/20260724-REPORT-long-term-memory-iteration-13.md` | 长期记忆Store/Worker/Interface、GenB测试台、远程PostgreSQL和四段真实链路验收。 |
| 核心组件一期生产硬化检查点 | `records/reports/20260724-REPORT-phase1-production-hardening-checkpoint.md` | 运行保护、生产身份、SLO/告警、秘密攻击集、安全依赖、SBOM、真实PG/Redis与外部门禁状态。 |
| 核心组件管理端Iteration 6计划 | `records/plans/20260723-PLAN-core-component-console-iteration-6.md` | 交付固定五系统/14组件目录页，并落实“设计可表达外键、实际DDL无物理外键”的数据库门禁。 |
| 核心组件详情Iteration 7计划 | `records/plans/20260723-PLAN-core-component-detail-iteration-7.md` | 从目录卡片进入详情，通过聚合读接口展示实现、配置、绑定和审计。 |
| Genesis 与 Gen-C 统一授权改造前基线 | `records/baselines/20260720-genesis-genc-unified-authorization-baseline.md` | GenB/GenC Git 状态、本地 PostgreSQL 与 GenC SQLite 可恢复备份和校验值。 |
| Genesis 与 Gen-C 统一登录实现 | `records/reports/20260714-REPORT-genesis-genc-sso-implementation.md` | Gen-C 一次性 ticket、首次自动建用户、数据隔离、测试和本地端到端验收。 |
| Genesis 统一登录全链路说明 | `records/reports/20260715-REPORT-genesis-unified-login-chain-document.md` | 面向开发和非开发人员的三平台统一登录文档、流程图、接口和排查清单编写记录。 |
| Gen-B 客户端与 Genesis 中英文接入 | `records/reports/20260715-REPORT-client-genesis-i18n-integration.md` | 两个入口的共享语言、页面翻译、请求头、测试和浏览器验收记录。 |
| 客户端智能体英文数据补全 | `records/reports/20260715-REPORT-client-agent-english-data-completion.md` | 全量审计 80 条智能体，清理名称、描述和分类共 209 处中文残留。 |
| Genesis 用户权限列表性能优化 | `records/reports/20260720-REPORT-genesis-access-users-performance-optimization.md` | 消除用户与平台权限组装的 N+1 查询，将远程库列表响应从约 15 秒降至约 1.1 秒。 |
| 新增 shizhenhua、sunny 并提交权限优化 | `records/reports/20260720-REPORT-add-shizhenhua-sunny-and-commit-access-optimization.md` | 两名统一门户/GenO 管理员创建、映射、登录验收及性能优化提交记录。 |
| 补齐三名统一用户与平台权限 | `records/reports/20260727-REPORT-add-three-genesis-platform-users.md` | 为黄令湖、徐浩健、胡正尧新增 GenB/Genesis 管理员，分配 GenC `ADMIN` 并绑定既有 GenO 用户，完成真实登录和门户验收。 |
| 核心组件需求确认与门户动效优化 | `records/reports/20260727-REPORT-core-component-confirmation-and-portal-motion-performance.md` | 整理只聚焦结构和功能效果的评审清单，定位登录页全屏Canvas持续重绘卡顿并完成性能回归、双语构建和页面验收。 |
| GenC、GenO 生产部署报告 | `records/reports/20260721-REPORT-genc-geno-production-deployment.md` | 两个平台最新统一登录代码部署、同域 Cookie 修正和完整 SSO 验收。 |
| GenO 推送与仓库外交接 | `records/reports/20260721-REPORT-geno-push-and-external-handoff.md` | protected `dev` 推送限制、仓库外交接文档和提交边界检查。 |
| Genesis 本地部署中心 | `records/reports/20260721-REPORT-local-deployment-center.md` | 无服务 PowerShell 桌面工具、三个项目脚本、DPAPI、安全门禁、Dry Run 和验证记录。 |
| 三项目正常分支提交与推送 | `records/reports/20260721-REPORT-push-three-project-normal-branches.md` | GenB `create-genB`、GenC `main` 推送核验及 GenO `dev` protected branch 权限阻塞记录。 |
| Genesis 统一登录门户性能优化 | `records/reports/20260721-REPORT-genesis-portal-login-performance.md` | 批量授权、映射和翻译查询，消除登录后重复平台请求，页面关键等待由约 5.73 秒降至约 1.94 秒。 |
| GenB 品牌、门户短入口和权限页工具栏 | `records/reports/20260721-REPORT-genb-brand-portal-route-toolbar.md` | 页签统一为 Genesis Engine，增加 `/portal/login` 正式入口，并固定两个平台用户操作按钮同组显示。 |
| Genesis 门户稳定短 URL 实施 | `records/reports/20260721-REPORT-genesis-portal-stable-short-url.md` | 动态分离 Vue Router 与构建基路径，使短入口挂载和登录后 URL 保持不变。 |
| GenO JDK 21、WSL 与 CDP 本地环境 | `records/reports/20260721-REPORT-local-jdk21-wsl-cdp-environment.md` | D 盘 JDK 21、Ubuntu WSL、Bash、Node.js、reasoning 构建验证及 WSL 读取 Windows Chrome UUID 的兼容修复。 |
| 三项目交接与本地知识库 | `records/reports/20260722-REPORT-three-project-handoffs-and-local-knowledge-bases.md` | GenB/GenC/GenO 三份脱敏交接，以及 GenC、GenO 不进入 Git 的本地 AI 知识库。 |
| 三项目私密部署拓扑 | `records/reports/20260722-REPORT-private-three-project-deployment-topology.md` | 建立本机私密部署架构与凭据文档；报告不包含秘密正文。 |
| 三项目完整交接重构 | `records/reports/20260722-REPORT-comprehensive-three-project-handoffs.md` | 补全 GenB 数据库，按代码/运维/安全最佳实践重写三份可执行交接。 |
| GenB 中英文双版本 Nginx 路由诊断 | `records/reports/20260722-REPORT-genb-en-nginx-route-diagnosis.md` | 确认英文公开 URL、未加载的 Nginx location 和错误 `/genb/` 构建 base，给出不影响中文版本的修正顺序。 |
| GenB 单源码中英文双构建代码审查 | `records/reports/20260722-REPORT-genb-bilingual-build-code-review.md` | 安全快进 `6a145f1`，验证四项构建和 API/base，并记录中文视觉污染、语言存储、HTML 元信息和脚本问题。 |
| GenB 五大系统与14个组件总体设计 | `records/reports/20260723-REPORT-core-memory-components-detailed-design.md` | 采用arc42、C4和KEP组合模板，定义14组件全量验收并细化一期长短记忆设计。 |
| Control System长短记忆开发实施指南 | `records/reports/20260723-REPORT-control-system-memory-implementation-guide.md` | 将总体设计落实为2200余行开发指南，覆盖代码架构、双身份、数据、Interface、测试、部署和其他系统复用模板。 |
| 核心组件平台全栈开发总纲 | `records/reports/20260723-REPORT-core-component-platform-development-guide.md` | 将范围扩展到GenB控制面、五大系统/14组件执行面、智能体编排面和平台全量交付，并把记忆指南调整为一期专项。 |
| 自建Inference Engine设计更新 | `records/reports/20260723-REPORT-self-hosted-inference-engine-design-update.md` | 将Runtime System最小Inference Engine提前到一期，统一模型调用，Alaya降为可选Adapter并同步设计、开发、验收和路线图。 |
| Runtime Inference Iteration 1 | `records/reports/20260723-REPORT-runtime-inference-iteration-1.md` | 新建runtime-system-service，完成Fake Provider下非流式、结构化、Embedding、模型目录、健康和SSE纵向切片及15项测试。 |
| Runtime Inference Iteration 2 | `records/reports/20260723-REPORT-runtime-inference-iteration-2.md` | 完成OpenAI-compatible Direct Provider、版本化路由、env secretRef、动态模型目录、错误归一和32项离线测试；真实Provider门禁仍待完成。 |
| GenB核心组件控制面Iteration 3 | `records/reports/20260723-REPORT-genb-core-component-control-plane-iteration-3.md` | 完成五系统/14组件目录、Implementation注册、配置发布、智能体绑定、RBAC和89项GenB后端测试；M3治理能力继续迭代。 |
| GenB核心组件治理Iteration 4 | `records/reports/20260723-REPORT-genb-core-component-governance-iteration-4.md` | 完成Implementation与绑定启停、配置历史与回滚、脱敏管理审计和93项GenB后端测试。 |
| GenB服务凭证与组件会话Iteration 5 | `records/reports/20260723-REPORT-genb-component-access-iteration-5.md` | 完成一次性服务凭证、bcrypt哈希、吊销、scope/Actor/绑定门禁、独立签名短时组件会话和101项测试。 |
| GenB核心组件管理端Iteration 6 | `records/reports/20260723-REPORT-core-component-console-iteration-6.md` | 完成五系统/14组件真实目录页、双语筛选与浏览器验收，并将7张控制面表迁移为无物理外键。 |
| GenB核心组件详情Iteration 7 | `records/reports/20260723-REPORT-core-component-detail-iteration-7.md` | 完成组件治理聚合读接口、实现/配置/绑定/审计四标签页及真实浏览器链路。 |
| GenB核心组件详情治理Iteration 8 | `records/reports/20260723-REPORT-core-component-governance-console-iteration-8.md` | 完成Implementation注册/启停、配置发布/回滚、智能体绑定/启停和真实页面验收。 |
| Control System短期记忆Iteration 9 | `records/reports/20260723-REPORT-control-system-short-term-memory-iteration-9.md` | 新建Control System执行面，完成双凭证、短期记忆Interface、四维隔离、Redis Adapter和16项测试；真实GenB身份联调仍受门禁限制。 |
| GenB与Control System身份契约Iteration 10 | `records/reports/20260723-REPORT-genb-control-system-identity-iteration-10.md` | 完成RS256 Actor Token、JWKS、受保护凭证内省、Control System HTTP Adapter和双项目129项测试，为测试智能体联调解除身份门禁。 |
| 核心组件真实测试智能体Iteration 11 | `records/reports/20260723-REPORT-control-system-test-agent-iteration-11.md` | 新建单代码多实例测试智能体，贯通真实GenB、Control System、开发PostgreSQL和Redis，完成A/B召回隔离及失败矩阵验收。 |
| 核心记忆测试台与测试智能体操作手册 | `records/reports/20260724-REPORT-core-memory-testing-guide.md` | 核对当前页面、接口和测试智能体运行形态，交付逐点击手册、教学页和快速参考，并明确STOPPED与CLI启动边界。 |
| 智能体级长期服务凭证与页面闭环 | `records/reports/20260724-REPORT-agent-long-lived-service-credential.md` | 将临时组件scope凭证改为每agent单活长期机器身份，绑定动态授权，并完成页面生成/轮换/复制/自动填入和远程库迁移。 |
| Short-term Memory Iteration 12 | `records/reports/20260724-REPORT-short-term-memory-iteration-12.md` | 完成管理测试台、已发布动态配置、Runtime摘要、Redis摘要、指标/trace和真实五段链路验收，并修复绑定重配置状态机。 |
| 核心组件本地403与菜单层级修复 | `records/reports/20260723-REPORT-core-component-load-menu-fix.md` | 修复9100同源入口Token键不一致导致的403，并完成“智能体中心→智能体列表/核心组件”菜单层级调整。 |
| Genesis 英文统一登录短入口 | `records/reports/20260723-REPORT-genesis-english-short-entry.md` | 通过 Nginx 查询参数为英文客户端提供 `/portal/login?lang=en` 短入口，并保留既有资源、API 和兼容入口。 |
| Genesis 英文路径与备份保留策略 | `records/reports/20260727-REPORT-genesis-english-path-and-backup-retention.md` | 合并同事最新代码，发布 `/portal/en/login`，收敛前端/Nginx备份并记录后端凭据阻塞。 |

## Runtime/CLI

| 主题 | 文件 | 说明 |
|---|---|---|
| 生产底座改造报告 | `records/reports/20260708-REPORT-runtime-cli-production-foundation.md` | Runtime/CLI 安全、执行链路、Policy、Workflow、Memory、LLM 等改造总结。 |

## 部署

| 主题 | 文件 | 说明 |
|---|---|---|
| 部署记录入口 | `records/deployments/README.md` | 部署记录目录说明。 |
| 三项目本地 BAT 启动 | `records/reports/20260722-REPORT-replace-control-web-with-local-bat.md` | 撤销本地控制网页，改用 GenB、GenC、GenO 三个 BAT。 |
| 三项目后台启停快捷方式 | `records/reports/20260722-REPORT-background-local-start-stop-shortcuts.md` | 隐藏启动、D 盘日志、PID 精准停止和桌面六个入口。 |
| Genesis SSO Token Exchange 部署 | `records/deployments/20260709-DEPLOY-genesis-sso-exchange.md` | 前端和后端部署、token exchange 验证和回滚方式。 |
| GenB 前后端生产部署 | `records/deployments/20260721-DEPLOY-genb-frontend-backend.md` | GenB 后端、客户端、管理端部署及 Genesis 接口验收。 |
| GenC、GenO 统一登录生产部署 | `records/deployments/20260721-DEPLOY-genc-geno-unified-login.md` | GenC、GenO 后端与前端部署、备份、同域代理和完整 SSO 验收。 |
| Genesis 统一门户登录性能优化部署 | `records/deployments/20260721-DEPLOY-genesis-portal-login-performance.md` | 直接发布现成 JAR 和客户端 dist，记录备份、哈希、健康检查及线上登录验收。 |
| GenB 品牌、门户短入口和权限页工具栏部署 | `records/deployments/20260721-DEPLOY-genb-brand-portal-route-toolbar.md` | 部署两个前端和 Nginx 精确短入口，记录产物、备份及线上验证。 |
| Genesis 门户稳定短 URL 部署 | `records/deployments/20260721-DEPLOY-genesis-portal-stable-short-url.md` | 仅部署客户端动态路由基路径产物，浏览器验证挂载和登录后短 URL 不变。 |
| GenB 英文客户端部署 | `records/deployments/20260722-DEPLOY-genb-english-client.md` | 新增 `/genb-client-en/` 独立英文产物和共享后端代理，保留中文客户端、门户和管理端不变。 |
| GenB 客户端固定语言与管理端入口部署 | `records/deployments/20260722-DEPLOY-genb-client-fixed-language-console-entry.md` | 移除中英文语言切换按钮，按后端管理端权限显示对应语言的管理端入口，并完成管理员/普通用户浏览器验收。 |
| GenC 角色菜单权限管理部署 | `records/deployments/20260722-DEPLOY-genc-role-permission-management.md` | 提交并部署 GenC `ADMIN/USER` 角色权限配置，发布共享后端及中英文管理端，完成管理员/普通用户接口和双语页面验收。 |
| Genesis 英文统一登录短入口部署 | `records/deployments/20260723-DEPLOY-genesis-english-short-entry.md` | Nginx 按 `lang=en` 返回英文客户端入口，记录配置备份、回归结果和回滚方式。 |
| Genesis 英文路径部署与前端备份清理 | `records/deployments/20260727-DEPLOY-genesis-english-path-and-backup-cleanup.md` | 发布 `/portal/en/login`，保留兼容入口，前端各组件和Nginx仅保留最新1–2版备份。 |

## Bug 和问题追踪

| 主题 | 文件 | 说明 |
|---|---|---|
| Bug 记录入口 | `records/bugs/README.md` | Bug 记录目录说明。 |
| GenC SSO callback 卡住 | `records/bugs/20260721-BUG-genc-sso-callback-stuck.md` | 公网慢连接占住唯一同步 Gunicorn worker，导致 health 与统一登录全部超时的诊断证据和处理建议。 |
| Genesis 用户权限列表 N+1 | `records/bugs/20260720-BUG-genesis-access-users-n-plus-one-latency.md` | 10 人列表约 162 条 SQL、15 秒延迟的诊断、修复和真实接口验收。 |
| 核心组件本地9100鉴权与菜单层级 | `records/bugs/20260723-BUG-core-component-local-9100-auth-and-menu-hierarchy.md` | 客户端与管理端Token键不一致导致目录403，以及菜单父子层级修复记录。 |

后续每次修复线上或本地 bug，必须新增：

```text
records/bugs/YYYYMMDD-BUG-主题.md
```

## 决策

| 主题 | 文件 | 说明 |
|---|---|---|
| 决策记录入口 | `records/decisions/README.md` | ADR 目录说明。 |
| 核心记忆组件集中式Runtime API（已替代） | `records/decisions/20260723-ADR-centralized-memory-runtime-api.md` | 历史方案，已由“Control System直接提供组件Interface”ADR替代。 |
| Control System直接提供组件Interface | `records/decisions/20260723-ADR-control-system-component-service.md` | 当前有效决策：删除Memory Runtime Service中间层，由Control System Service内部两个深Module直接提供长短记忆Interface。 |
| 核心组件平台三面分离 | `records/decisions/20260723-ADR-core-component-platform-three-planes.md` | 当前有效决策：GenB控制面、五大系统执行面和智能体编排面分离；公共契约复用但不使用重型Runtime SDK。 |
| 自建最小Inference Engine | `records/decisions/20260723-ADR-self-hosted-inference-engine.md` | 当前有效决策：一期提前交付Runtime Inference Engine；Direct Provider为主、Alaya为可选Adapter，Control和智能体不持有上游模型凭证。 |

后续发生长期架构、部署、安全或数据模型决策时，新增：

```text
records/decisions/YYYYMMDD-ADR-主题.md
```

## 按问题类型查找

| 问题类型 | 优先看 |
|---|---|
| 不知道项目结构 | `PROJECT_INDEX.md`、`PROJECT_OVERVIEW.md`、`docs/PROJECT_STRUCTURE.md` |
| 不知道某次文档为什么这么写 | `records/reports/20260708-REPORT-engineering-knowledge-base.md` |
| API/数据库/权限文档来源 | `records/reports/20260708-REPORT-api-db-permission-detail.md` |
| Genesis 门户视觉和接入文档变更 | `records/reports/20260709-REPORT-genesis-portal-logo-and-genco-guide.md` |
| 英文版后端返回和数据库怎么改 | `docs/requirements/BACKEND_DATABASE_I18N_PLAN.md`、`records/reports/20260710-REPORT-backend-database-i18n-plan.md` |
| 客户端和 Genesis 中英文怎么接入 | `docs/development/CLIENT_GENESIS_I18N_IMPLEMENTATION.md`、`records/reports/20260715-REPORT-client-genesis-i18n-integration.md` |
| 英文智能体卡片仍显示中文 | `docs/development/BACKEND_DATABASE_I18N_IMPLEMENTATION.md`、`records/reports/20260715-REPORT-client-agent-english-data-completion.md` |
| Runtime/CLI 改造进度 | `records/reports/20260708-REPORT-runtime-cli-production-foundation.md` |
| 部署历史 | `records/deployments/` |
| Bug 历史 | `records/bugs/` |

## 维护规则

- 新增报告后，必须把主题加到本文件。
- 新增 Bug 后，必须按问题类型归类。
- 新增部署记录后，必须写服务器、路径、包名、命令、验证和回滚点。
- 记录只描述历史事实，不覆盖当前代码判断。
