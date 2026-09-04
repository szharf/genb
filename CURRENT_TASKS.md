# 当前任务看板

## 任务：撤下 GenB 管理端核心组件模块并重新部署

- 日期：2026-09-04
- 当前状态：已完成代码修改、远端提交、中英文重新部署和生产回归。
- 目标：管理端中英文不展示核心组件菜单，不能通过历史深层地址进入核心组件页面，生产构建不再生成核心组件页面代码块。
- 修改边界：只修改并部署 GenB 管理端中英文；不修改客户端、后端、数据库、Nginx，不部署或启动核心组件模型。
- 组件边界：`navigationModel.js` 管理菜单真源，`MainLayout.vue` 渲染菜单，`router/index.js` 控制可访问页面，`api/index.js` 控制主构建公共 API 依赖。
- 计划：`records/plans/20260904-PLAN-撤下管理端核心组件模块.md`。
- 验收结果：12 个管理端 Node 测试文件和中英文构建通过；线上两套产物均为 47 个文件，核心组件视图/API 扫描为 0；管理端及其他项目入口均为 HTTP 200。

## 任务：修复管理端 Docker 大文件上传链路

- 日期：2026-09-04
- 当前状态：已完成代码修改、Git 推送、前后端生产部署和边界回归验收。
- 精确现象：新前端服务器对 `100 MiB + 1 byte` 的上传请求立即返回 HTTP 413，实际有效上限为 100 MiB，并非 1 GiB。
- 根因：同事已处理前端进度、后端 5 GB 上限和 `transferTo`，但新前端 Nginx 仍为 `client_max_body_size 100m`；同时默认请求缓冲和后端内存型 `/tmp` 会放大大文件上传的磁盘、内存风险。
- 修改边界：仅调整 GenB Docker 上传精确路由和 multipart 临时目录；不放宽其他接口，不修改其他项目路由，不上传或导入 Docker 镜像。
- 计划：`records/plans/20260904-PLAN-管理端Docker大文件上传修复.md`。
- 验收结果：上传精确路由的 `1 GiB + 1 byte` 声明请求不再返回 413；超过 5 GiB 仍返回 413，普通 API 的 `100 MiB + 1 byte` 仍返回 413；后端健康及九个既有前端入口均为 200。

## 任务：合并同事最新代码并部署 GenB 后端

- 日期：2026-09-04
- 当前状态：代码合并、数据库迁移、依赖补齐、生产部署和接口验收均已完成。
- Git：在既有 `shizhenhua` 分支合并远端 `create-genB`，合并提交 `10ad7e9c`；智能体排序修复提交 `a8127cef`，均已推送远端。
- 后端：生产 JAR SHA256 为 `d0b108a70d214e993ba7e5c1ebd074148736b5a5b5e772c5fb693918169bd31a`，`8581/api/actuator/health` 返回 `200 UP`。
- 数据库：已显式执行统一用户约束迁移，补齐首次改密字段和有效外部映射唯一索引；迁移前已有 PostgreSQL 备份。
- 运行依赖：新增 GenB 专用 `genb-redis`，仅绑定 `127.0.0.1:6379`，未开放公网端口。
- 验收：完整后端测试 180 项，0 失败、1 跳过；86 个智能体中 10 个运行中，排序违规 0；核心组件接口不再 404，未登录按预期返回 403；MCP 和智能体接口返回 200。
- 部署边界：没有部署或启动核心组件模型；服务器原有 `knowledge_app` 不属于本次新增。
- 独立遗留：`admin1` 使用历史测试口令仍返回业务码 401，需单独核验账号状态或重置流程，不影响本次后端健康和路由验收。
- 记录：`records/deployments/20260904-部署-合并同事代码并更新GenB后端.md`。

## 任务：客户端智能体按部署端口打开

- 日期：2026-09-04
- 当前状态：客户端代码修复、中英文构建、生产部署和真实浏览器验收均已完成。
- 变更：普通智能体优先使用 `accessUrl`，未登记时打开 `http://47.116.69.17:{port}/`；不再进入生产尚未部署的 `/agents/{agentId}/` 数据面路由。
- 部署边界：只发布 GenB 客户端中英文；管理端中英文目录指纹未变化，管理端核心组件模型、后端、数据库和 Nginx 均未部署。
- 验收：客户端完整测试 47/47；生产“智能审单专家”点击地址为 `http://47.116.69.17:8052/`，目标服务 HTTP 200；其他项目回归通过。
- 记录：`records/deployments/20260904-部署-客户端智能体按运行端口访问.md`。

## 任务：恢复 FIBO 前端路由

- 日期：2026-09-01
- 当前状态：已完成生产修复和全量回归。
- 根因：FIBO 静态文件、后端和受限 SSH 隧道均正常，但统一 Nginx 配置中的 `/fibo/` location 在此前覆盖中丢失。
- 修复：恢复 `/fibo`、`/fibo/`、`/fibo/index.html` 和 `/fibo/api/`；未修改其他项目路由。
- 验收：FIBO 页面和 API 均为 HTTP 200，真实浏览器显示后端正常连接；统一登录、GenB、GenC、GenO 与两个官网回归通过。
- 记录：`records/deployments/20260901-修复-FIBO前端路由恢复.md`。

## 任务：两个官网域名补齐统一登录与平台路由

- 日期：2026-09-01
- 当前状态：已完成生产配置更新和验收。
- 变更：`alaya.to` 与 `genesis-engine.ai` 保留各自官网首页，并通过共享 Nginx 路由补齐 `/portal`、GenB 中英文、Genesis 客户端中英文和 GenO 入口；现有 GenC `/journey/` 未改动。
- 验收：两个官网首页、统一登录、GenB、GenO、GenC 均为 HTTP 200；GenB 两个健康代理均为 `200 UP`；真实浏览器确认两个域名的统一登录页面正常渲染。
- 记录：`records/deployments/20260901-部署-两个官网域名补齐平台路由.md`。

## 任务：统一登录 GenO 切换到新前端服务器

- 日期：2026-09-01
- 当前状态：已完成生产配置更新和端到端验收。
- 变更：GenB 的 GenO callback 及平台入口数据已切到 `http://18.167.156.11/geno/sso/callback`；GenO 后端 CORS 已加入新前端来源。
- 验收：Genesis Ticket、GenO 换票和 profile 均为 HTTP 200；最终进入 `http://18.167.156.11/geno/overview`，刷新后登录态保持。
- 记录：`records/deployments/20260901-部署-统一登录GenO切换新前端.md`。

## 阅读入口（2026-08-24）

- 当前执行只看本文件最前面的“仅 GenB 容量例外生产部署”和“统一数据面网关受控上线”；后续条目是历史任务快照，不代表仍待执行。
- 当前唯一允许恢复的生产动作是“仅 GenB”计划，但其 M0 Gate A 未通过，服务器仍保持零修改；恢复条件见对应 M0 报告。
- 统一数据面本地实现已完成 M0-M5 和 Gate A-F，生产上线仍被后端容量 Gate 阻塞，不得根据本地完成状态直接部署。
- 查当前结论先读 `PROJECT_INDEX.md` 的“当前工作树”，查历史证据再读 `records/RECORDS_INDEX.md`，不要从聊天记录补架构或部署决定。
- 同事交付入口位于 `gen-b/项目说明.md` 和 `gen-b/创建所需表.sql`；压缩包是本地交付物，不纳入 Git。

## 任务：Genesis 统一模块新增用户功能

- 日期：2026-08-25
- 当前状态：本地 M0-M5 与 Gate A-F 已完成；后端 179 项测试（其中 1 项按原条件跳过）、管理端 18 项测试、客户端 43 项测试及中英文构建通过。尚未执行生产数据库迁移和生产部署，等待独立上线审批。
- 目标：管理员在“统一门户权限”中一次创建 GenB/Genesis 用户，原子配置 GenC 角色和既有 GenO 用户映射，并强制新用户首次登录修改密码。
- 核心边界：GenB 是账号源；GenO 只读目录并绑定，不创建或修改 GenO 用户；生产部署不在本计划授权范围内。
- 计划：`records/plans/20260825-PLAN-genesis-unified-user-provisioning.md`。
- 完成报告：`records/reports/20260828-REPORT-genesis-unified-user-provisioning.md`。

## 任务：补齐张涛统一用户与平台权限

- 日期：2026-08-24
- 当前状态：已完成。写入前确认 GenO 中 `zhangtao` 是唯一、启用的同名 `admin` 用户；随后新增 GenB `ADMIN` 源用户、同步 Genesis、配置 GenC `ADMIN` 和 GenO 精确映射。
- 回归结果：黄令湖、徐浩健、胡正尧、张涛四人的 GenB/Genesis 登录均通过；GenC 均为 `ADMIN`、解析 4 项权限并解锁；GenO 均精确绑定唯一同名启用 `admin` 用户并解锁。
- 变更边界：仅修改共享远程数据；未重置前三人密码，未创建或修改 GenO 用户，未部署代码、Nginx 或其他服务。
- 验收记录：`records/reports/20260824-REPORT-add-zhangtao-unified-platform-user.md`。

## 任务：仅 GenB 容量例外生产部署

- 日期：2026-08-18
- 计划：`records/plans/20260818-PLAN-genb-only-capacity-exception-production-deployment.md`
- 当前状态：M0已执行，Gate A未通过；未上传或修改服务器。后端根分区已达到95%硬停止线；客户端39/41通过，两个失败揭示当前客户端依赖本轮不部署的`/agents/{agentId}/`入口，直接发布会使现有智能体入口回归。等待容量恢复及客户端发布范围确认。
- 本轮范围：仅 GenB 后端、管理端/客户端中英文静态产物、必要的数据库增量迁移和必要时的 GenB Nginx 精确路由调整。
- 明确排除：统一数据面网关、专用 Redis、Runtime、核心组件服务、18714及其他智能体、GenC、GenO、GitLab和其他项目资产。
- 容量边界：原 Gate B仍未通过；当前约94%/6.2GiB仅按一次容量例外评估。部署前及每阶段必须保持根分区低于95%、可用不少于5GiB，预计峰值新增不超过1GiB，否则停止。
- 前置阻塞：必须冻结可追溯发布快照，并在生产数据副本验证新增SQL与旧生产JAR的回滚兼容性；不通过不得上线。
- M0证据：`records/reports/20260818-REPORT-genb-only-deployment-m0.md`。

## 任务：统一数据面网关受控上线

- 日期：2026-08-12
- 当前状态：本地实现M0-M5与Gate A-F全部通过。上线前检查M0 Gate A通过；M1已删除23个精确校验的GenB旧JAR并安装三个GenB日志的项目专用logrotate，释放约1.42GiB，GenB未重启且健康与统一登录回归通过。后端根分区仍为91%、仅余8.7GiB，Gate B未通过；已停止扩大清理范围，当前等待单独批准云盘快照和扩容。仍不得生产部署。
- 总体方案：前端服务器仅保留Nginx和静态入口；后端以一个轻量部署单元承载智能体访问与核心组件调用两个内部模块；GenB只作控制面；使用L1进程缓存与专用Redis；按智能体和能力逐步迁移。
- 执行顺序：本地方案实现Gate F → 上线前检查与服务器治理Gate D → 生产部署Gate A-E。先完成全部本地代码、测试、镜像和样例配置；部署前再检查并治理服务器；两个前置Gate均通过后才允许生产切流。
- 上线检查计划：`records/plans/20260812-PLAN-production-readiness-inspection-and-remediation.md`
- 上线检查治理范围已收紧为GenB/Genesis白名单资产；不进入GenC、GenO、GitLab、其他智能体、其他团队Docker资产或现有Redis清理。GenB自身释放空间不足时必须停止并转磁盘扩容。
- 方案实现计划：`records/plans/20260812-PLAN-unified-data-plane-gateway-implementation.md`
- 方案实现计划已按arc42、KEP和MADR结构扩展为详细开发基线，包含方案选择、现状到目标矩阵、信任关系、Module与Interface、四类运行时场景、GenB数据模型、缓存TTL、安全、兼容分类、质量指标和Gate A-F；开发不得依赖聊天记录补齐决定。
- 部署计划：`records/plans/20260812-PLAN-unified-data-plane-gateway-production-deployment.md`
- 当前边界：本地源码、合同、管理端和本地`genb_local.bank_agent_db`已完成实现；服务器仅执行了M0白名单只读盘点和公开健康请求，未修改生产Nginx、Redis、数据库、应用文件或运行容器。
- M0证据：`records/baselines/20260812-BASELINE-unified-data-plane-gateway-m0.md`、`records/decisions/20260812-ADR-unified-data-plane-gateway.md`、`docs/security/UNIFIED_DATA_PLANE_GATEWAY_THREAT_MODEL.md`及`contracts/`数据面合同；未操作服务器、生产Nginx、生产Redis、生产数据库或运行容器。
- M1证据：`gen-b/gen-b-backend`数据面控制Interface及集成测试、`gen-b/gen-b-console`治理表单与构建、`gen-b/gen-b-backend/src/main/resources/db/V20260812_01__create_data_plane_config_state.sql`和`V20260812_02__add_data_plane_implementation_metadata.sql`；迁移前备份保存在本机D盘且不纳入Git。
- M5完成报告：`records/reports/20260813-REPORT-unified-data-plane-gateway-m5.md`。原检查点报告保留为历史证据，真实三组件进程缺口已经闭合。
- 上线前M0报告：`records/reports/20260813-REPORT-production-readiness-m0.md`。Gate A已通过；Gate B受后端磁盘容量阻塞，下一步必须取得具体治理动作授权。
- 上线前M1记录：`records/deployments/20260813-DEPLOY-genb-whitelist-jar-and-log-governance.md`。23个旧JAR和项目专用日志轮转已完成；白名单治理不足以达到容量水位，下一步只能扩容，不得清理其他项目。

## 任务：统一登录超时恢复与三项目线上验证

- 日期：2026-08-10
- 当前状态：已完成。统一登录 12 秒超时定位为后端服务器根分区 100% 后 GenB Java 进程卡死；释放归档日志和缓存空间后，使用现有脚本精确重启 GenB。浏览器真实登录返回 200，GenB、GenC、GenO 连续三轮访问和健康检查均通过。
- 变更边界：未修改数据库、Nginx 配置、部署包和其他项目容器；删除了归档 systemd 日志、DNF 缓存和无容器引用的悬空镜像。
- 剩余风险：后端根分区仍为 98%，需要后续按业务归属清理 Docker 镜像/卷、构建产物和历史备份。
- Bug：`records/bugs/20260810-BUG-genesis-login-timeout-disk-full.md`
- 部署记录：`records/deployments/20260810-DEPLOY-genb-login-recovery-and-project-verification.md`

## 任务：三个核心组件独立服务收敛

- 计划：`records/plans/20260805-PLAN-three-core-component-service-convergence.md`
- 架构决定：十四个核心组件分别提供独立公共服务；五个系统只作为GenB分类。稳定code以当前GenB代码为真源。
- 开发范围：优先完善`SHORT_TERM_MEMORY`、`PLANNING_REASONING`和`LONG_TERM_MEMORY`中的Conversation Memory；Knowledge Base只定义内部Adapter合同，由同事实现。
- 当前状态：M0-M5已完成，Gate A-F全部通过。三个组件分别作为独立公共服务，由GenB登记、配置、绑定和签发组件会话；短期、长期会话记忆、规划与推理均通过专项、相关全量、Manifest/OpenAPI一致性和真实浏览器自然语言验收。18714使用一次性授权码、Redis服务端会话和HttpOnly Cookie接入统一门户；9100旧`/core-agent/`仅保留`410 Gone`墓碑，不再代理或提供第二套页面。M5验收同时保留统一登录识别修复和`riskLevel=UNKNOWN`保守归一化修复。完成报告：`records/reports/20260806-REPORT-three-core-component-service-convergence-m5.md`。
- 边界：保护当前脏工作树；仅本地开发和本地验收；不操作服务器或服务器数据库。

## 任务：18714非技术用户对话式核心能力验收

- 计划：`records/plans/20260803-PLAN-conversational-core-capability-acceptance.md`
- 目标：把当前工程实验台改为普通用户可理解的对话界面；用户只需聊天和点击自然语言建议，不填写Task ID、Session ID、JSON或组件操作码。
- 交互：三个入口分别表达“记住本次交流”“跨会话记住我”“一步步生成Skill”；每个入口以欢迎语、连续问答、阶段提示、结果卡片完成测试，技术证据收进折叠详情。
- 当前状态：已完成。主页面改为三个自然语言对话场景，内部自动维护测试标识；每个场景新增按统一登录用户隔离的Redis对话历史，可新建、切换、刷新恢复旧对话。长期记忆已用两个可见的独立对话完成真实召回，不再用分隔线伪装换会话。短期两轮记忆、Skill多轮澄清和异步回复隔离保持通过。自动化`59 passed`，完成报告：`records/reports/20260803-REPORT-conversational-core-capability-acceptance.md`。
- 边界：保留三个能力入口和服务端会话安全；不操作服务器及服务器数据库；不覆盖当前工作树已有修改。

## 任务：18714核心组件独立测试工作台

- 计划：`records/plans/20260803-PLAN-customer-agent-separated-component-test-workbench.md`
- 目标：在`http://localhost:18714/`把短期记忆、长期记忆、规划与推理测试拆成三个独立工作区；每区只展示自己的输入、调用步骤、结果和判定标准。
- 成功标准：长期记忆可独立执行“写入提取→跨Session检索”；短期记忆可独立执行“首轮提交→同任务召回”；规划与推理可独立执行`ANALYZE/CONVERSE/GENERATE/VALIDATE/REVISE`；三者共用统一门户HttpOnly会话但不共用测试表单或结果区。
- 执行方式：先建立页面分区和受保护组件测试HTTP接口的失败测试，再按短期、长期、规划纵向切片逐项实现；最后更新逐点击手册并用本地浏览器验收。
- 当前状态：已完成M0-M5。三个工作区和四个受保护Interface已上线；短期记忆两轮召回、长期记忆提取/跨Session检索、规划ANALYZE均通过真实Chrome验收。Runtime新增可配置JSON Object结构化输出并保留本地Schema校验；本地长期记忆发布配置已修正为`memory-extraction-default`。自动化结果：测试智能体53项、Runtime 45项、Control System 54项通过（另3项因外部环境条件跳过）。完成报告：`records/reports/20260803-REPORT-customer-agent-separated-component-test-workbench.md`。
- 边界：不操作服务器或服务器数据库；不在浏览器暴露Session Grant、服务凭证、Actor Token或Provider密钥；保留现有统一登录与综合客户智能体接口。

## 任务：长期记忆组合架构与对话记忆开发

- 计划：`records/plans/20260803-PLAN-long-term-memory-composition-and-conversation-memory.md`
- 目标：保持固定`LONG_TERM_MEMORY`组件和单一智能体绑定，内部明确区分Conversation Memory与Knowledge Base Memory；本轮完成现有对话记忆的来源建模、检索筛选和对外合同。
- 状态：本轮已完成。M0领域与基线、M1来源合同、M2来源筛选、M3 PostgreSQL合同均完成；先后取得缺失`sourceType`、非法`sourceTypes`和空来源筛选的红色证据，再实现转绿。Control System全量`54 passed, 3 skipped`，测试智能体全量`45 passed`；跳过项仅为未配置的本地真实PostgreSQL/Redis环境测试。M4更正/反馈与M5知识库Adapter另立合同后继续。
- 边界：本轮不伪造Knowledge Base Adapter已可用，不操作服务器或服务器数据库。

## 任务：18714客户智能体页面滚动逻辑与UI优化

- 现象：生成长Skill后滚动页面，浏览器窗口、对话区、Skill预览和右侧任务栏出现多重滚动；输入框获取焦点时可将整个应用推离视口，导致左栏提前结束和底部大面积空白。
- 成功标准：桌面端文档本身不滚动；左栏、工作区和输入区始终位于同一动态视口；对话、Skill正文和任务栏各自只在需要时内部滚动；长内容生成后自动定位到最新结果；窄屏仍可用。
- 设计方向：深青控制台 + 纸感内容区，保留现有品牌识别，统一层级、字号、阴影、边界和滚动条。
- 当前状态：已完成。修复了文档级外层滚动和Grid自动排版导致的工作台高度折半；长Skill渲染后滚动延后到当前帧全部DOM插入完成后执行。完成深青控制台/纸感内容区的宽度、层级、阴影、字号、滚动条和动态视口优化。页面专项20项、Python全量45项通过；真实Chrome桌面视口中工作台、右栏和输入区底部全部与视口底部对齐，文档`scrollY=0`；窄屏由workbench内部滚动且输入区保持sticky。

## Bug：18714缺失智能体会话时未自动进入统一登录

- 现象：统一门户已登录，直接访问`http://localhost:18714/`时页面只显示“请先通过统一门户登录后使用智能体”，没有按既定SSO合同自动跳转。
- 成功标准：无有效智能体客户会话时，`GET /`返回`303 -> /auth/login`；有效会话时正常返回客户页面；手动登录链路和退出链路不回归。
- 执行方式：先增加失败HTTP测试，再修复根路由会话门禁，最后运行Python专项/全量与真实Chrome验收。
- 当前状态：已完成。红色基线稳定复现`GET /`错误返回200；修复后无会话返回`303 -> /auth/login`，有效会话仍返回客户页面。`tests/test_web.py` 17项、Python全量42项通过；本地18714已重启且健康为`UP`。Chrome新建自动化标签的`127.0.0.1 -> localhost`跨主机回调被浏览器扩展拦截为`ERR_BLOCKED_BY_CLIENT`，未计为浏览器全链路通过；原有Chrome有效会话刷新已通过。

## 临时硬性约束：演示冻结

- 冻结时间：2026-07-31 当前时间至 2026-08-01 23:59（Asia/Shanghai）。
- 冻结期间禁止连接、部署、重启、修改或清理服务器，禁止读写服务器数据库。
- 仅允许本地代码开发、本地数据库操作和本地服务验证；即使本地验收通过，也不得向服务器发布。
- 2026-08-02 00:00 后该临时约束自动过期；恢复服务器操作前仍需重新核对用户授权、服务器状态和部署范围。

## 任务：独立智能体访问入口与统一门户SSO改造

详细计划：`records/plans/20260731-PLAN-independent-agent-entry-and-portal-sso.md`

当前状态：2026-08-03已完成M0-M8并通过Gate A-D。18714是客户智能体唯一入口；9100旧同源代理返回410且不再提供智能体页面。Java 147项、客户端41项、Python 41项、中英文构建、真实HTTP安全矩阵和浏览器登录/刷新/聊天/退出均通过。完成报告：`records/reports/20260803-REPORT-independent-agent-entry-and-portal-sso.md`。

### 暂停快照（2026-07-31 17:58，Asia/Shanghai）

- M2已实现一次性授权码/会话授权合同、Redis Hash存储、60秒Code、原子消费、8小时Session Grant、服务凭证校验、精确回调校验和注销撤销；支持本地实际智能体状态`AUTHORIZED + RUNNING`，同时兼容`PUBLISHED + RUNNING`。
- M2已新增Session Grant解析域逻辑：必须同时验证服务凭证、Grant所属智能体、用户启用/未锁定状态及当前智能体权限。`AgentSsoServiceTest`最新3项通过。
- M2尚未完成：安全审计事件未接入；带密码的真实Redis并发消费测试仍因未提供`GENB_TEST_REDIS_PASSWORD`而跳过；组件会话Controller/Security尚未接通Session Grant。
- M3已实现18714登录跳转、state校验回调、Redis服务端会话、不透明`HttpOnly + SameSite=Lax` Cookie、最小会话查询、聊天Cookie鉴权和注销撤销；浏览器脚本不再读取或发送Genesis/GenB LocalStorage Bearer Token。
- 独立智能体完整测试最新结果：`36 passed`。隔离测试环境位于`D:\code\opencode\genb\.venv-control-agent`，安装记录已写入`D:\default\Documents\install_download_log.md`。
- 可编辑安装生成了未跟踪目录`control-system-test-agent/src/genb_control_system_test_agent.egg-info/`；这是本地测试构建产物，不是交付源码，恢复后应在确认路径后清理或加入合适忽略规则。
- 当前测试先行停点：已新增`ComponentSessionControllerTest`，用于要求`X-Agent-Session-Grant`在无浏览器Bearer Token时解析用户；该测试尚未运行，生产`ComponentSessionController`也尚未接线，因此此刻Java全量并非已验证绿灯。
- 当前18714聊天仍临时把Session Grant放进现有`user_token`参数，`GenBClient`仍按Bearer发送；恢复后必须先把它改为专用`X-Agent-Session-Grant`头并让后端Controller显式分流，不能把此中间态用于验收。
- 该暂停快照记录时未启动、停止或重启任何本地演示服务；9100旧同源代理入口当时仍保留，现已在Gate C后删除。

恢复时第一步：运行新增`ComponentSessionControllerTest`取得红色证据，然后接通Controller/Security与Python专用Session Grant头；之后补M2审计和真实Redis原子测试。只有M2、M3全部通过并完成18714真实登录/刷新/聊天/退出验收后，才评估Gate B。

### 1. 目标

- 将客户智能体唯一入口从9100旧同源代理切换为智能体自行托管的`http://localhost:18714/`。
- 通过一次性授权码、服务端Redis会话和HttpOnly Cookie接入9100统一门户，不跨Origin共享LocalStorage Token。
- GenB继续管理智能体权限、服务凭证、核心组件绑定和访问地址；智能体独立提供页面、登录会话和聊天接口。
- 新入口验收通过后删除9100旧代理和旧登录逻辑，不保留双入口。

### 2. 执行顺序

- [x] M0：建立9100成功路径和18714跨Origin登录失败的自动化基线。
- [x] M1：固化SSO合同、威胁模型、错误码、TTL、回调白名单、Cookie和日志脱敏规则。
- [x] M2：实现GenB一次性授权码、智能体权限/状态校验、服务凭证兑换、Redis原子消费和脱敏审计；负向安全矩阵通过，真实Redis并发消费仅一个成功。
- [x] M3：实现并真实验收18714登录/回调/退出、Redis服务端会话、HttpOnly Cookie及聊天接口会话鉴权。
- [x] M4：实现并真实验收统一门户智能体SSO中转和统一退出。
- [x] M5：增加`accessUrl/callbackUrl`并将GenB“访问智能体”改为跳转独立地址。
- [x] M6：删除9100旧同源代理、旧链接和跨Origin LocalStorage兑换逻辑，启动脚本只输出18714。
- [x] M7：完成Java/Vue/Python、真实HTTP和浏览器登录/权限/聊天/退出矩阵验收。
- [x] M8：更新设计、开发、操作文档、报告、Changelog和索引，精确核对变更。

### 3. 完成标准

- [x] 已登录门户时通过智能体入口进入18714，未登录时登录后返回18714。
- [x] Token和服务凭证不进入URL、LocalStorage、普通Cookie、页面、日志或Git。
- [x] 授权码一次性、短期有效并绑定用户、agent、state和精确回调；重放和篡改失败。
- [x] 刷新保持智能体会话，退出后18714和GenB受保护地址均不可直接进入。
- [x] 短期记忆、规划与Runtime真实调用继续受服务凭证、绑定、scope和Actor Token门禁。
- [x] 9100旧智能体入口、代理和文档引用全部删除，不存在新旧两个版本。
- [x] 只完成本地开发和验收，未操作服务器及服务器数据库。

## 任务：规划与推理动态需求澄清及客户智能体体验重构

详细计划：`records/plans/20260731-PLAN-planning-dynamic-clarification-and-core-agent-ux.md`

### 1. 目标

- 将规划与推理组件从“固定三问 + 当前消息关键词判断”改为“任务级需求状态 + 内部受控检索 + 大模型动态追问 + Skill生成/校验/版本”。
- 同一`taskId`跨多轮、跨`sessionId`累计用户已确认需求，不重复询问已回答问题，不把模型推断伪装为用户事实。
- 简单且信息完整的需求直接生成Skill；复杂需求检索已审核模板、组件Interface、授权HTTP API/MCP/SDK和开发规范后再生成。
- 优化或重构客户智能体任务页面，使需求澄清、进度、问题回答和Skill结果对非开发用户清晰可用。

### 2. 执行顺序

- [x] M0：补充计划、确认现状基线，并以失败测试复现固定三问、多轮信息丢失和页面关键交互问题。
- [x] M1：新增任务级需求草稿、事实来源/确认状态、问题状态和持久化；实际DDL不创建物理外键。
- [x] M2：新增可替换的规划知识检索Interface及一期本地已审核模板/规范Adapter，为未来Tool Registry接入保留Seam。
- [x] M3：接入结构化需求分析提示词和动态追问，删除固定问题主逻辑及关键词清空逻辑。
- [x] M4：增强简单/复杂Skill生成提示词、授权资源引用、确定性校验、有限修复和DRAFT版本保存。
- [x] M5：调整客户智能体编排，使规划对话按`taskId`持续推进，并返回可展示的需求进度、问题和参考信息。
- [x] M6：重构客户页面信息架构、会话状态、错误/加载/空状态、问题交互、Skill结果和响应式布局。
- [x] M7：运行规划服务、测试智能体及页面自动化测试，并在当时的9100旧同源代理入口完成真实浏览器验收。
- [x] M8：更新设计、开发、操作文档、报告和索引，精确检查变更范围。

完成报告：`records/reports/20260731-REPORT-planning-dynamic-clarification-and-core-agent-ux.md`。

### 3. 验收标准

- 用户不使用“输入为/输出为/约束”等固定句式时，系统仍能从自然语言正确累计已确认需求。
- 用户分多轮回答时只追问真实缺口；每轮最多三个针对当前业务的问题，不重复固定三问。
- 简单Skill可直接生成；复杂Skill能引用已授权模板、组件或工具，并拒绝把未授权工具写为可执行声明。
- 跨`sessionId`但相同`taskId`可继续，换`taskId`不串数据；未绑定组件、无凭证和模型失败路径保持门禁。
- 页面能明确展示当前任务、已确认信息、待回答问题、生成进度、Skill草稿和可理解错误，不暴露凭证或原始思维链。
- 自动化测试、真实本地HTTP和当时的9100旧同源代理入口浏览器操作全部通过并留存验收证据。

### 4. 当前约束

- 本任务只允许本地代码、数据库和服务验证；演示冻结期间不连接、不读取、不修改、不部署服务器及服务器数据库。
- 规划与推理组件只生成、校验和修订Skill，不执行Skill、HTTP API或MCP工具。
- 一期检索仅使用管理员审核或系统内已发布资料；不允许运行时任意互联网搜索。
- 设计可表达数据关系，实际数据库表和迁移脚本不创建物理外键。

## 任务：GenB 数据库本地化与本地测试智能体清理

### 1. 目标

- 修复两个测试智能体中文名称被写成 `???` 的问题，并防止本地启动脚本再次错误写入。
- 将当前服务器 GenB PostgreSQL 数据完整备份、恢复并切换到本地 PostgreSQL，日常开发不再写服务器数据库。
- 本地接口和页面验收通过后，只清理服务器上 `standalone-planning-test-agent` 与 `core-component-demo-agent` 及其明确从属数据，不删除共享组件实现、配置或服务数据。

### 2. 执行顺序

- [x] 确认乱码根因并修复当前记录；生成服务器数据库迁移前完整备份。
- [x] 验证启动脚本 UTF-8 修复，核对三个智能体访问入口。
- [x] 恢复服务器备份到本地 PostgreSQL，并核对表、记录数和关键数据。
- [x] 将 GenB 后端默认连接切换为本地数据库，重启并完成登录、组件和智能体页面验收。
- [x] 对两个测试智能体做专项备份，事务清理服务器从属数据并核对删除数量。
- [x] 补充实施报告、Bug 记录和索引，精确提交相关文件。

### 3. 安全约束

- 必须先完成“远程备份可读、本地恢复成功、本地业务验收通过”，之后才能清理服务器数据。
- 服务器清理范围仅限两个已确认的本地测试智能体；任何共享实现、配置、组件目录和其他智能体都不在本次删除范围。
- 数据库表按设计可表达外键关系，实际表和迁移脚本不新增物理外键。

## 任务：客户可验收的核心组件智能体与真实模型链路

详细计划：`records/plans/20260730-PLAN-customer-ready-core-component-agent.md`

### 1. 目标

- 将现有开发接口测试页升级为客户可以直接使用的独立智能体：只通过自然语言聊天，不要求客户选择组件操作或填写JSON。
- 独立智能体项目自行提供前端与后端，GenB只负责入口、授权、组件注册、绑定和组件会话；本地可直接通过智能体独立端口访问。
- 使用Runtime System Inference Engine统一调用真实模型；短期记忆负责上下文存取，规划与推理负责需求澄清、Skill生成、校验和修订。
- 以真实模型、真实GenB绑定、真实Redis/PostgreSQL和客户可见结果完成端到端验收。

### 2. 当前进度

- M0-M7已完成：独立客户页面、真实模型、短期记忆、规划Skill、GenB三组件绑定、长期服务凭证、正反向验收和文档全部完成。
- 当前本地唯一入口：`http://localhost:18714/`；9100旧同源反向代理已删除。
- 当前真实运行：短期记忆`18705`、规划`18712`、Runtime推理`18704`、客户智能体`18714`；GenB后端`8581`、统一入口`9100`。
- 报告：`records/reports/20260730-REPORT-customer-ready-core-component-agent.md`。

### 3. 完成标准

- [x] 独立智能体地址可直接打开客户级聊天页面，页面不展示`ANALYZE/GENERATE/VALIDATE/REVISE`或原始JSON输入表单。
- [x] 同一个逻辑智能体通过GenB组件会话解析并调用`SHORT_TERM_MEMORY`、`PLANNING_REASONING`和`INFERENCE_ENGINE`的启用绑定。
- [x] 普通聊天真实调用模型；同一task跨session能够召回上下文，未绑定或错误凭证调用失败。
- [x] 规划对话能够主动澄清缺失需求，并由真实模型生成可校验Skill；规划组件仍不执行Skill或MCP。
- [x] 客户页面展示正常回答；管理员可展开查看脱敏后的组件、模型、trace和记忆命中证据。
- [x] 服务凭证和Provider API Key只保存在服务端运行环境，不进入浏览器、数据库配置JSON、日志和Git。
- [x] 单元、契约、集成、真实HTTP、浏览器和负向路径全部通过，形成操作手册和验收报告。

## 任务：规划与推理引擎接入 GenB 与测试智能体

详细计划：`records/plans/20260730-PLAN-planning-reasoning-genb-agent-integration.md`

### 1. 目标

- 将 `PLANNING_REASONING` 正式注册到 GenB，发布实现和配置并绑定专用测试智能体。
- 管理端支持管理员服务直测与智能体绑定测试，客户端提供真实规划测试智能体页面。
- 完整验证需求澄清、Skill生成、校验、失败修订，以及凭证/绑定负向路径。

### 2. 当前进度

- 已完成M0-M6：GenB适配器、专用测试智能体、管理端双模式测试台、客户端规划页面、注册绑定、真实HTTP与浏览器验收全部通过。
- 已完成M7：操作文档、验收报告、索引和精确提交清单已完成。

### 3. 完成标准

- [x] GenB 契约、实现、配置、绑定和长期服务凭证完整生效。
- [x] 管理员服务直测和智能体绑定测试均真实调用 `18712` 规划服务。
- [x] 专用测试智能体页面不接触服务凭证，能完成完整规划生命周期。
- [x] 自动化、双语构建、真实HTTP、浏览器和负向矩阵全部通过。
- [x] 操作文档、报告、索引和精确提交完整。

## 任务：规划与推理引擎独立服务一期

详细计划：`records/plans/20260730-PLAN-planning-reasoning-service-phase1.md`

### 1. 目标

- 新建固定组件`PLANNING_REASONING`的独立逻辑服务，归属Control System。
- 先澄清用户需求，再按简单或复杂场景生成可审计、可版本化的Skill文档。
- 复杂Skill可声明MCP工具和异常规则；规划引擎只生成、校验和修订，不执行工具。
- 复用GenB服务凭证、Actor Token和组件绑定身份模型。

### 2. 当前进度

- 已完成：服务、PostgreSQL持久化、GenB身份、OpenAPI、测试和本地HTTP验收。
- 当前运行：`127.0.0.1:18712`，`authoring=TEMPLATE`，`store=POSTGRESQL`。
- 本轮只开发和独立验收服务；GenB注册、页面测试台、智能体绑定联通另立任务。

### 3. 完成标准

- [x] 需求不完整时返回明确澄清问题，不能生成伪完整Skill。
- [x] 简单需求生成标准Skill，复杂需求使用带MCP、人工确认和异常恢复的模板。
- [x] 可校验Skill结构并基于失败事件生成新版本，旧版本保持可查询。
- [x] 生成结果不包含模型原始思维链，服务不执行任何工具。
- [x] OpenAPI、身份负向测试、全量自动化、操作文档、报告和提交完整。

## 任务：智能体绑定、统一退出、测试凭证与短期记忆聊天智能体

详细计划：`records/plans/20260730-PLAN-agent-binding-auth-credential-and-memory-chat.md`

### 1. 目标

- 绑定表显示智能体名称和ID。
- 管理端、客户端统一退出到`/portal/login`，管理端无Token不可进入受保护路由。
- 测试台按智能体自动保存和回填凭证，真实调用后不清空。
- 实现`standalone-memory-test-agent`聊天页面和真实短期记忆调用链。

### 2. 当前进度

- 已完成：五项功能开发、单元测试、中英文构建和真实浏览器端到端验收。
- 端口保持不变：`9100`唯一用户入口，`9000`仅为管理端内部上游。
- 测试智能体运行在`127.0.0.1:18711`，聊天入口为`/agents/standalone-memory-test-agent/chat`。

### 3. 完成标准

- [x] 绑定名称、退出跳转、未登录守卫、凭证保留均有自动化和浏览器证据。
- [x] 测试智能体同一会话两轮聊天能够证明短期记忆召回。
- [x] 服务凭证不下发到聊天页面，不写入数据库和提交文件。
- [x] 文档、报告、索引和提交完整。

## 任务：短期记忆运行联通与双模式测试台

详细计划：`records/plans/20260730-PLAN-short-term-memory-runtime-connection-and-dual-testbench.md`

### 1. 目标

将独立短期记忆服务真实注册到GenB，发布配置并绑定专用测试智能体；同时把现有仅支持智能体绑定的测试台拆成“管理员服务直测”和“智能体绑定测试”两条路径。

### 2. 完成标准

- [x] 管理员可不选择智能体、不填写服务凭证，直接测试已注册、启用的Implementation和已发布配置。
- [x] 智能体测试继续强制校验长期服务凭证、agentId、启用绑定、Implementation和配置。
- [x] 独立短期记忆服务验证GenB签名身份，不相信调用者自报身份Header。
- [x] 两种模式均真实完成短期记忆写入和跨session恢复。
- [x] 远程开发库只追加或更新本任务测试记录，实际表不创建物理外键。
- [x] 自动化、双语构建、真实Redis、浏览器逐点击和负向矩阵通过。
- [x] 更新零基础点击操作手册、验收报告和索引。

### 3. 当前进度

- 已完成：M0-M6全部工作，管理员服务直测和智能体绑定测试均已真实通过。
- 当前运行：6379、8581、9000、9100、18705；`9100`是唯一用户入口，统一门户由客户端承载，`/genb/*`在内部转发到`9000`的最新管理端源码。`9000`只是本地内部上游，不是另一版本入口。
- 报告：`records/reports/20260730-REPORT-short-term-memory-runtime-connection-and-dual-testbench.md`。

## 任务：独立短期记忆服务与核心组件接口契约模板

详细计划：`records/plans/20260730-PLAN-standalone-short-term-memory-and-component-contract-template.md`

### 1. 目标

按照“固定核心组件 → 稳定接口契约 → 可替换服务实现”的三层结构，新建一个独立短期记忆服务，并为 GenB 核心组件模块增加 OpenAPI 接口契约注册、解析、发布和接口查看能力。两个项目先独立完成、独立测试，暂不建立真实调用或绑定链路。

### 2. 完成标准

- [x] 独立短期记忆服务提供会话上下文、回合提交、跨会话任务工作台读取/保存/删除以及健康和 OpenAPI 接口。
- [x] 隔离键至少包含 `tenantId + agentId + userId + taskId`，`sessionId` 作为任务下的对话标识；密码、验证码和 Token 不持久化。
- [x] GenB 可以通过OpenAPI 3.0/3.1 JSON/YAML上传、粘贴或带默认值的手工填写创建契约草稿，解析多个接口、校验后发布并查看历史版本。
- [x] 服务实现必须声明支持的契约版本；本轮不让 GenB 调用新短期记忆服务。
- [x] 管理端提供接口契约、接口列表和实现注册操作入口，页面状态与后端接口一致。
- [x] 后端、短期记忆服务、管理端自动化测试及中英文构建通过。
- [x] 编写面向零基础管理员的逐点击、逐字段注册操作手册，并完成真实页面验收。

### 3. Interface 与模块边界

- `short-term-memory-service`：短期记忆数据面，只通过自己的 HTTP Interface 保存和读取短期记忆及任务工作台；它是独立逻辑服务，不代表所有组件必须独立成系统项目。
- GenB `Core Component Contract`：固定组件的稳定 Interface 真源，保存 OpenAPI 文档、版本、状态和解析后的操作摘要。
- GenB `Component Implementation`：部署实现注册，只保存实现身份、地址、健康地址和支持的契约版本。
- GenB 管理端：负责契约录入、校验、发布、接口浏览和实现注册，不承载短期记忆业务逻辑。
- 本轮明确不做：GenB 到新服务的运行时调用、智能体真实绑定调用、SDK 或 MCP Adapter。

### 4. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 固化范围和公开 Interface | 已完成 | 用户已确认逻辑服务、三种录入方式和暂不连通边界 |
| 2 | 新建短期记忆服务 | 已完成 | 8项HTTP/Service/真实Redis测试、OpenAPI |
| 3 | GenB 契约管理后端 | 已完成 | Spring Boot全量122项与无物理外键测试 |
| 4 | GenB 契约管理页面 | 已完成 | 4项纯逻辑测试、三种录入方式和双语构建 |
| 5 | 全量验证与真实页面验收 | 已完成 | JSON粘贴、YAML上传、发布、查看和实现版本下拉 |
| 6 | 零基础操作手册和报告 | 已完成 | 样例、逐点击手册、报告与索引 |

### 5. 当前进度

- 已完成：独立短期记忆服务、Redis Adapter、GenB契约控制面、管理端三种录入方式、双语构建和真实页面验收。
- 未连通：未注册短期记忆真实实现、未创建配置或智能体绑定、未修改测试台和测试智能体调用路径。
- 报告：`records/reports/20260730-REPORT-standalone-short-term-memory-and-interface-contract-template.md`。
- 已确认：支持OpenAPI 3.0/3.1 JSON/YAML上传、粘贴和带默认值的手工填写；后台规范化为OpenAPI JSON，一个实现声明支持一个已发布契约版本。
- 安全约束：实际建表不创建物理外键；不提交凭证、私钥、数据库密码或本地运行产物。

## 任务：同步同事最新代码并发布英文统一登录路径 `/portal/en/login`

### 1. 目标

在保留本地已完成的核心组件与登录页性能改动前提下，同步公司远端 `create-genB` 最新提交，为英文统一登录增加稳定路径 `http://16.162.33.130/portal/en/login`，并保持中文 `/portal/login`、临时查询参数入口和旧客户端入口兼容。

### 2. 完成标准

- [x] 公司远端最新 `create-genB` 已安全合入当前正常协作分支，双方提交历史和既有工作区文件均保留。
- [x] `/portal/en/login` 使用根 Router history base 并匹配公开登录路由。
- [x] 中文 `/portal/login`、英文 `/portal/en/login` 和旧入口路由行为测试通过。
- [x] 客户端完整测试及中英文生产构建通过。
- [x] 英文产物和 Nginx 精确入口完成备份部署，`nginx -t` 与 reload 通过。
- [x] 新旧入口、主静态资源、API 和管理端回归通过。
- [x] 前端各 GenB 组件和 Nginx 只保留最新 1–2 版备份，旧临时上传包已删除。
- [ ] GenB 后端只保留最新 1–2 版备份；当前保存的 root 密码被服务器拒绝，尚未取得目录清单或执行删除。
- [x] 报告、部署记录、长期部署文档与索引完成。

### 3. 组件边界

- `routerBase.ts`：纯函数判断哪些短入口使用根 history base。
- `router/index.ts`：声明统一登录公开路由及英文路径别名，不承载语言选择逻辑。
- Nginx：将 `/portal/en/login` 精确映射到英文客户端 `index.html`；静态资源和 API 继续复用 `/genb-client-en/`。

### 4. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | fetch 并审计本地/远端分叉与脏文件 | 已完成 | 本地 ahead 14、behind 3；源文件无目标路由重叠 |
| 2 | 暂存生成物并普通合并同事提交 | 已完成 | `4225ebb`；生成物恢复且 stash 保留 |
| 3 | RED→GREEN 增加英文短路径 | 已完成 | 2项测试先失败；实现后5项定向测试通过 |
| 4 | 完整测试及中英文构建 | 已完成 | Vitest 27项、vue-tsc、两项 Vite build通过 |
| 5 | 备份并部署英文产物和 Nginx | 已完成 | 目录/配置备份、`nginx -t`、reload通过 |
| 6 | 线上与浏览器验收 | 已完成（HTTP/产物） | 新旧URL、英文bundle、资源、API、管理端均通过；CDP受WSL网络异常阻塞 |
| 7 | 更新文档、报告和索引 | 已完成 | records 和部署指南可追溯 |
| 8 | 清理前端与Nginx旧备份 | 已完成 | 删除17个目录、7个配置备份和5个临时包，保留每组最新1–2版 |
| 9 | 清理GenB后端旧备份 | 阻塞 | 私密文档中的root密码被服务器拒绝，需更新授权凭据 |

### 5. 当前进度

- 进行中：等待有效的 GenB 后端服务器 root 凭据，以盘点并清理 `/app/gen-b-console` 旧备份。
- 已完成：公司远端合并 `4225ebb`、短路径实现提交 `cb416d8`、27项测试、中英文构建、英文产物/Nginx部署、HTTP回归和前端备份清理。
- 阻塞：`47.116.69.17` 拒绝本机私密拓扑中保存的 root 密码；未绕过认证、未对后端执行删除。

### 6. 风险和遗留问题

当前分支已经普通合并双方历史，没有 reset 或强制覆盖。英文短入口只隐藏页面入口路径，英文静态资源和 API 仍保留 `/genb-client-en/` 前缀。前端旧备份已永久删除，仅剩保留版本可用于回滚；后端清理必须在取得有效授权凭据后继续。

## 任务：核心组件需求确认文档与统一门户登录动效性能优化

### 1. 目标

将五大系统/14组件总体结构、规划与推理引擎、短期记忆/工作台的功能边界和效果验收问题整理为正式评审文档；复现并优化 Genesis 统一门户登录页鼠标移动卡顿，保持现有视觉和登录功能。

### 2. 完成标准

- [x] 评审文档只聚焦结构、功能边界、用户效果和一期验收，不要求领导决定项目拆分、HTTP/MCP、数据库等技术实现。
- [x] 文档进入项目索引和历史记录索引，可供会议直接逐项确认。
- [x] 建立可重复的登录页鼠标移动性能测试并记录优化前基线。
- [x] 确认卡顿根因并进行最小范围优化，保留品牌视觉且兼容减少动态效果设置。
- [x] 登录输入、语言入口、构建和浏览器性能回归通过。
- [x] 写实施报告并精确提交相关源文件和文档。

### 3. 页面组件边界

- `PortalLoginView.vue`：登录页布局和功能组合，不承载动画循环。
- `PortalWaveBackground.vue`：背景Canvas绘制、可见性和动效降级策略，是本次性能诊断的主要测试对象。
- `PortalLoginForm.vue`：用户名、密码和提交交互，行为保持不变。

### 4. 完成结果

- 已完成：确认清单已写入 `docs/requirements/CORE_COMPONENT_STRUCTURE_PLANNING_SHORT_TERM_CONFIRMATION.md`。
- 已完成：确认卡顿来自全屏Canvas持续高负载绘制，而非鼠标跟随逻辑；固定波浪改为30 FPS、低密度和高DPI上限，后台暂停，减少动态效果时只绘制一帧。
- 已验证：性能回归通过，前端23项测试、中英文构建和真实页面视觉验收通过。
- 报告：`records/reports/20260727-REPORT-core-component-confirmation-and-portal-motion-performance.md`。

## 任务：补齐黄令湖、徐浩健、胡正尧统一用户与平台权限

### 1. 目标

在共享远程环境中为黄令湖、徐浩健、胡正尧建立 GenB 源用户并同步到 Genesis，分配 GenC `ADMIN` 平台角色，并绑定三人已经存在的 GenO `admin` 用户；不重复创建 GenO 账号，不改动其他用户权限。

### 2. 完成标准

- [x] 只读确认 GenB/Genesis 中三人不存在，GenO 中三人账号唯一存在且角色为 `admin`。
- [x] 创建并启用三个 GenB `ADMIN` 用户，用户名与现有 GenO 账号一致。
- [x] 通过正式同步链路建立三个 Genesis 用户及 GenB 映射。
- [x] 三人 `GEN_C` 入口解锁，平台角色为 `ADMIN`，权限解析完整。
- [x] 三人 `GEN_O` 映射指向已有同名账号且入口解锁。
- [x] 完成登录、权限查询和映射验收，记录实际结果且不记录密码或 Token。

### 3. 安全约束

- 仅追加三名目标用户和对应授权，不删除、不覆盖其他用户数据。
- GenO 已有账号只建立映射，不重新创建或重置密码。
- 初始密码不写入报告、Git 或日志；交付后要求用户本人修改。
- 操作前后按用户名逐项查询，发现同名冲突立即停止。

### 4. 完成结果

- 已完成：2026-07-27 通过共享远程环境真实接口验收，三人 GenB/Genesis 登录成功，GenC `ADMIN` 权限和 GenO 既有用户映射全部生效。
- 记录：`records/reports/20260727-REPORT-add-three-genesis-platform-users.md`。

## 任务：智能体级长期服务凭证与管理端获取闭环

### 1. 目标

将服务凭证从临时验收夹具改为智能体级长期机器身份：每个智能体只保留一份当前有效凭证，凭证与 `agentId` 匹配后，再由 GenB 根据已启用组件绑定决定是否允许调用；管理端提供生成、一次展示/复制、轮换、吊销和状态查看，独立测试台不再要求用户读取本地 JSON 文件。

### 2. 完成标准

- [x] 同一智能体最多只有一份当前有效服务凭证；重新生成等价于安全轮换，旧凭证立即失效。
- [x] 服务凭证默认长期有效，不要求每次页面测试或每个组件重新签发。
- [x] 服务凭证只证明智能体身份；组件是否可调用由已启用绑定、Implementation 和已发布配置动态决定。
- [x] 未绑定或绑定停用时请求失败；新增绑定后无需重新签发智能体凭证。
- [x] 管理端可按智能体查看当前凭证状态、生成或轮换，并只在生成当次展示与复制明文。
- [x] 独立测试台生成后自动填入凭证，页面刷新后不从后端恢复明文。
- [x] 后端、Control System、前端测试及本地页面验收通过。
- [x] 设计、开发、操作文档和报告与新模型一致。

### 3. 当前进度

- 已完成：远程开发库已非破坏性收敛为每智能体一份ACTIVE长期凭证；GenB、Control和中英文管理端已实现并通过自动化及真实页面测试。

### 4. 组件边界

- `ServiceCredentialService`：智能体级凭证签发、单活轮换、认证、吊销和审计。
- `ComponentSessionService`：根据已启用绑定动态解析组件和 Actor Token 权限，不把服务凭证绑定到单个组件。
- Control System `CompositeIdentityVerifier`：服务凭证验证智能体身份，Actor Token 验证本次绑定组件与动作。
- `CoreComponentCredentialControl.vue`：查看状态、生成/轮换、一次展示和复制，向测试表单上送新凭证。
- `CoreComponentTestForm.vue`：保留测试输入与提交职责，不持有凭证管理副作用。

## 任务：核心组件独立测试台与测试智能体详细操作手册

### 1. 目标

面向不了解核心组件实现的管理员和测试人员，提供一份可以逐项照做的长短期记忆测试手册，解释页面每个输入、数据来源、操作原因、预期结果、自动化测试智能体、证据保存和失败排查。

### 2. 完成标准

- [x] 页面短期记忆测试覆盖首次写入、同Session召回、Session隔离和智能体隔离。
- [x] 页面长期记忆测试覆盖提取、写入、召回和跨Session演示，并明确页面测试边界。
- [x] 说明服务凭证、登录Token、绑定智能体和测试Session的获取方法及安全要求。
- [x] 说明测试智能体的交互式调用、短期完整矩阵和长期完整矩阵。
- [x] 提供结果判定、证据模板、清理步骤和故障排查表。
- [x] 正式运行手册、教学版页面、快速参考和索引一致。

### 3. 当前进度

- 已完成：已依据当前页面、GenB 测试运行器和测试智能体源码交付正式手册、教学页与快速参考；已明确测试智能体当前是按命令运行的 CLI，不需要在智能体列表中启动为常驻进程。

## 任务：核心组件平台 Iteration 14——M7 一期生产硬化与上线门禁

### 1. 目标

在 Short-term Memory、Long-term Memory、Inference Engine Service 三个一期组件完成真实纵向切片后，补齐生产前必须具备的限流、容量、可观测、安全、部署制品、备份恢复和回滚能力，并将需要 Provider、数据合规、SRE 或安全负责人签字的外部门禁与技术验收分开记录。未经真实 Provider 和责任人确认，不把一期标记为可上线。

### 2. 工作包

| 工作包 | Module/边界 | 完成标准 | 状态 |
|---|---|---|---|
| WP1 门禁基线 | 将总体设计 27.6 和 M7 条目转成可执行矩阵，区分自动化、演练和外部签字 | 每项有 owner、证据、状态和阻塞原因 | 已完成 |
| WP2 运行保护 | Runtime/Control 的请求大小、并发、速率、超时、队列积压和成本上限 | 超限 fail-closed，错误稳定，配置非法时启动失败 | 进行中：单进程保护已完成，集群配额/费用待外部门禁 |
| WP3 可观测与告警 | 指标、健康、积压、延迟、错误、降级和脱敏日志 | 自动测试、dashboard/alert 规则和秘密零泄漏扫描 | 已完成 |
| WP4 安全硬化 | 身份吊销缓存边界、注入输入、越权、秘密、依赖和配置审查 | 攻击/权限矩阵自动化通过，无明文凭证证据 | 已完成：自动化门禁；正式渗透仍为外部门禁 |
| WP5 部署与恢复 | 镜像、SBOM、配置/OpenAPI校验和PG/Redis备份恢复说明 | 可重复构建；开发环境完成非破坏性恢复演练 | 进行中：Python锁/SBOM/零漏洞完成，镜像与恢复环境外部阻塞 |
| WP6 灰度与回滚 | 配置、绑定、Implementation路由、进程和数据污染处置 | 使用测试命名空间完成演练并形成证据 | 进行中：控制面22项专项测试通过 |
| WP7 一期总验收 | 27.6逐项复核、全量回归和报告 | 技术项关闭；外部签字项明确为上线阻塞 | 未开始 |

### 3. 约束

- 不操作生产部署；演练仅使用本地临时端口、测试命名空间、远程开发 PostgreSQL 追加数据和本地 Redis 独立逻辑库。
- 真实建表仍不得创建物理外键；恢复演练不得删除或覆盖既有远程数据。
- Fake Provider 只能验证故障和结构化契约，不能替代真实 Direct Provider、费用负责人和数据合规签字。
- 不提交密码、Token、API Key、私钥或临时凭证；日志、指标、SBOM和报告也不得包含秘密。

### 4. 完成标准

- [x] 一期门禁矩阵已建立，并能从需求追踪到自动测试、演练报告或外部签字。
- [ ] 三个一期组件具备有界资源、限流/超时、SLO指标、告警规则和运维手册。
- [ ] 越权、吊销、提示词注入、秘密零泄漏和依赖故障矩阵通过。
- [ ] OpenAPI、配置Schema、镜像/SBOM、数据库迁移和恢复材料可追溯。
- [ ] 配置、绑定、路由、进程、凭证和数据污染回滚完成非破坏性演练。
- [ ] 自动化与真实依赖回归通过；所有不能由代码关闭的上线门禁有明确责任人和状态。

### 5. 当前验证

- 安全依赖基线：FastAPI `0.135.4`、Starlette `1.3.1`、Cryptography `48.0.1`；Runtime/Control锁文件和CycloneDX SBOM已生成。
- `pip-audit`：两服务均为`No known vulnerabilities found`。
- 安全依赖隔离环境回归：Runtime `42 passed`；Control含远程PostgreSQL与本地真实Redis `55 passed`。
- GenB配置回滚、Implementation启停、绑定/凭证闭环专项测试：`22 passed`。
- 监控与发布门禁资产测试：`5 passed`；技术门禁`10/10 PASS`。
- 生产门禁仍未通过：真实Provider/合规签字、生产网关与Secrets、不可变镜像/OS层扫描、批准的备份恢复环境、目标容量与72小时稳定性证据尚缺。

## 任务：核心组件平台 Iteration 13——Long-term Memory纵向切片与提取Worker

### 1. 目标

在已完成的GenB控制面、可信组件会话、Runtime Inference Adapter和Short-term Memory基础上，交付Long-term Memory一期完整纵向切片：智能体提交脱敏后的可见对话，异步提取用户偏好/稳定事实/用户约束，持久化到远程PostgreSQL，并能按tenant/user/agent隔离检索、过期和删除。

### 2. 工作包

| 工作包 | Module/边界 | 完成标准 | 状态 |
|---|---|---|---|
| WP1 契约与迁移 | Long-term公开Interface、错误、配置Schema和显式SQL迁移；设计可标逻辑关系，实际表无物理外键 | 迁移幂等、回滚/前向修复说明、远程开发库只追加 | 已完成 |
| WP2 Long-term Store | Module拥有Repository Port，PostgreSQL Adapter实现三维隔离、去重、版本、TTL/retention和软删除 | In-memory/PostgreSQL合同、跨agent/user/tenant隔离和删除测试 | 已完成 |
| WP3 Extraction Job/Worker | 接收任务202、租约领取、Runtime结构化提取、敏感拒绝、置信度和UPSERT/NO_WRITE | 幂等、重试上限、旧租约恢复、失败不影响短期记忆 | 已完成 |
| WP4 Search/Delete Interface | 搜索只返回允许类型和未过期记录；用户删除与管理员审计删除闭环 | scope、Actor Token、分页/上限、删除审计和不存在幂等 | 已完成 |
| WP5 GenB与测试台 | 注册/发布Long-term真实Implementation和配置，扩展测试智能体/管理测试台 | 跨会话召回、A/B隔离、敏感信息不落库、页面演示 | 已完成 |
| WP6 验收收口 | 自动化、远程PostgreSQL、Runtime HTTP、秘密/SDK/FK扫描、报告与提交 | M5出口矩阵全部通过 | 已完成 |

### 3. 一期边界

- 一期只保存`USER_PREFERENCE`、`STABLE_FACT`、`USER_CONSTRAINT`，不保存密码、验证码、Token、API Key、隐藏CoT或模型原始响应。
- Long-term Memory是Control System内的深Module，不新增Memory Runtime Service，不使用旧Runtime SDK。
- 模型调用只经我方Runtime Inference Interface；Fake仅用于自动化/本地验收，生产不得伪造提取成功。
- 真实建表不得创建物理外键；所有隔离条件由Repository查询和合同测试强制。
- Iteration 13先交付结构化用户长期记忆，不把M13完整RAG摄取、向量索引、引用治理冒充为已完成。

### 4. 完成标准

- [x] 提取任务快速返回202，Worker可恢复、幂等、有限重试并记录NO_WRITE/失败原因。
- [x] 三类长期记忆通过严格Schema、敏感过滤、置信度阈值和保留期后入库。
- [x] tenant/user/agent任一不同均不可检索或删除他人记录。
- [x] PostgreSQL实际表无物理外键；迁移和业务测试使用远程开发库只追加、不直接删既有数据。
- [x] GenB发布配置控制类型、阈值、保留期、topK、自动提取、模型别名和失败策略。
- [x] 测试台与Test Agent完成跨session召回、A/B隔离、敏感拒绝、删除和Runtime故障演示。
- [x] 全量回归、可观测、秘密/SDK/FK扫描、报告和精确提交通过。

## 任务：核心组件平台 Iteration 12——短期记忆摘要、运行配置、管理端测试台与可观测性

### 1. 目标

把Iteration 11已经跑通的Short-term Memory从“可由脚本联调”提升为“管理员可在页面安全测试、运行参数来自发布配置、超预算历史可摘要、关键结果可观测”，关闭M4/M6在进入Long-term Memory前的主要缺口。

### 2. 工作包

| 工作包 | Module/边界 | 完成标准 | 状态 |
|---|---|---|---|
| WP1 管理测试Interface | GenB签发组件会话并通过小Invoker调用Short-term Memory；秘密仅写入不回显 | `component.test`后端权限、成功/失败/脱敏测试 | 已完成 |
| WP2 管理端测试台 | 详情页只负责组合；Form/Result组件与`useCoreComponentTestBench`分离 | 管理员选择绑定、输入一次性凭证/会话/消息并看到步骤结果 | 已完成 |
| WP3 动态运行配置 | Control System通过受保护GenB Interface读取绑定的已发布配置并按版本缓存 | TTL、maxTurns、maxContextTokens生效，失效/错误fail-closed | 已完成 |
| WP4 摘要与可观测性 | Summary Port隐藏Inference Adapter；Redis保存摘要；日志/指标不含正文 | 超预算摘要、模型失败降级、指标/健康/故障测试通过 | 已完成 |

### 3. Vue组件边界

| 组件/Composable | 单一职责 | 数据流 |
|---|---|---|
| `CoreComponentTestBench.vue` | Feature容器，组合表单和结果 | 接收组件详情，调用Composable |
| `CoreComponentTestForm.vue` | 收集绑定、session、消息和一次性凭证 | props down，`run` event up |
| `CoreComponentTestResult.vue` | 只展示脱敏步骤、上下文数量、回答和耗时 | 只读props |
| `useCoreComponentTestBench.js` | 唯一异步状态源、API调用和错误归一 | 返回readonly状态和显式`run/reset`动作 |

### 4. 完成标准

- [x] 管理员可从Short-term Memory详情页运行真实测试，普通用户及缺`component.test`权限用户被后端拒绝。
- [x] 服务凭证使用密码输入且不持久化；请求、响应、错误、审计和页面均不回显凭证/Actor Token。
- [x] 测试台使用真实绑定、发布配置和Control System，不提供绕过鉴权的mock成功。
- [x] 发布配置可控制短期记忆TTL、窗口和上下文预算，非法配置及GenB不可用fail-closed。
- [x] 超预算旧对话可以摘要，摘要失败时保留最近窗口并明确降级，不能提交伪造摘要。
- [x] 自动测试、真实页面、真实Redis、秘密/SDK扫描、报告和精确提交全部通过。

### 5. 边界

- 不把服务凭证保存到数据库、LocalStorage、日志或测试证据。
- 不在GenB实现记忆业务；GenB测试Interface只做授权、组件会话与调用编排。
- 不在Vue路由页堆积表单和API状态，遵循Composition API与props down/events up。
- 本轮不实现Long-term Memory、完整RAG或生产部署，不创建物理外键。

## 任务：核心组件平台 Iteration 11——真实测试智能体与短期记忆端到端验收

### 1. 目标

交付一套可配置为多个逻辑实例的`control-system-test-agent`，通过真实GenB登录态与各自服务凭证换取组件会话，再调用真实Control System Short-term Memory；完成Agent A连续对话、Agent B隔离、未绑定/错凭证/越权拒绝和Redis残留检查，形成可重复执行的端到端验收证据。

### 2. 范围和边界

- 测试智能体是轻量HTTP调用方，不依赖或复制旧Runtime SDK，不承载Redis、鉴权或记忆业务规则。
- A/B使用同一代码产物，仅通过`agentId`与各自服务凭证区分；不得复制项目目录，不得共用服务凭证。
- 用户JWT、服务凭证和内部Token只从运行时参数/环境变量注入，测试报告只记录脱敏标识。
- GenB负责Implementation、配置、绑定、凭证和组件会话；Control System负责Short-term Memory数据面。
- 本轮先用可重复的确定性回答器验证记忆链，不把模型Provider可用性混入记忆验收；真实模型编排在后续短期记忆摘要工作包接入。
- 真实联调使用现有开发PostgreSQL和本地Redis，只追加具有`memory-test-*`命名空间的数据，不删除既有远程数据，不创建物理外键，不部署生产环境。

### 3. 完成标准

- [x] Test Agent客户端合同测试覆盖登录态传递、组件会话、双凭证、超时、错误映射和秘密不泄露。
- [x] 同一代码可用不同`agentId`/服务凭证运行A/B，不接受共享或错配凭证。
- [x] Agent A提交后同会话可召回，换会话不可召回；Agent B不能召回Agent A内容。
- [x] 未绑定、停用绑定、scope不足、错服务凭证和过期Actor Token均fail-closed。
- [x] 真实GenB、Control System、PostgreSQL、Redis联调通过，Redis测试键在验收后按测试命名空间清理且不影响其他数据。
- [x] 三项目全量回归、旧SDK扫描、秘密扫描、报告、索引和精确提交完成。

### 4. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 固化Test Agent Interface、配置和降级边界 | 已完成 | 设计文档与公开契约对齐 |
| 2 | RED→GREEN：GenB/Control HTTP客户端与编排Module | 已完成 | 8项客户端/Module测试 |
| 3 | RED→GREEN：A/B隔离和失败矩阵验收器 | 已完成 | 9项真实E2E断言全部通过 |
| 4 | 本地真实进程、远程PostgreSQL与Redis联调 | 已完成 | 独立18581/18701拓扑与脱敏证据 |
| 5 | 全量回归、审查、文档和精确提交 | 已完成 | GenB 108、Control 21、Agent 8；提交`b703819` |

### 5. 后续总执行顺序

Iteration 11完成后依次推进：Short-term Memory摘要/配置/测试台 → Long-term Memory与提取Worker → 一期M6/M7生产硬化与验收 → M8—M12其余组件 → M13完整RAG → M14五系统14组件总验收。每一阶段均按“任务板→测试先行→实现→真实联调→报告→提交”关闭，不把规划卡片计为已实现组件。

## 任务：核心组件平台 Iteration 10——GenB非对称身份契约与Control System接入

### 1. 目标

把Iteration 9的本地身份Adapter替换为可真实联调的GenB身份契约：GenB使用RS256签发Actor Token并发布JWKS，通过受保护内部Interface内省服务凭证；Control System通过HTTP/JWKS Adapter验证二者，为真实测试智能体联调解除身份门禁。

### 2. 范围和边界

- 保留现有`POST /v1/client/agents/{agentId}/component-session`响应结构，将其中Actor Token升级为RS256。
- Actor Token固定`iss=genb`、`aud=control-system`，包含`tenantId/userId/agentId/sessionId/components/jti/iat/nbf/exp`并带`kid`。
- 新增公开只读JWKS Interface；只发布RSA公钥参数，不返回私钥、路径或环境配置。
- 新增内部服务凭证内省Interface，通过独立内部Bearer凭证保护；无效/过期/吊销凭证统一返回`active=false`。
- `tenantId`一期由GenB受信服务端配置提供，不接受客户端请求体覆盖；后续接真实租户目录时替换该Adapter。
- Control System新增GenB HTTP内省和JWKS公钥加载Adapter，失败或未知`kid`一律fail-closed。
- 统一短期记忆scope为GenB现有规范：`component:short-term-memory:read|write|delete`。
- 本轮不部署、不修改远程数据库、不新增表或物理外键，不实现在线Actor Token吊销和密钥自动轮换。

### 3. Module与Seam

| Module/Adapter | 职责 |
|---|---|
| GenB `ActorTokenModule` | 在一个小Interface后隐藏RSA密钥加载、JWT claims、`kid`和JWKS表示 |
| GenB `CredentialIntrospectionModule` | 验证内部调用方和agent服务凭证，返回最小内省结果 |
| Control `GenBIntrospectionAdapter` | 通过内部HTTP Interface内省凭证，超时/错误fail-closed |
| Control `JwksActorTokenAdapter` | 按`kid`选择受信RSA公钥并验证固定算法、issuer、audience和时效 |

### 4. 完成标准

- [x] 现有组件会话交换成功，Actor Token为RS256且包含完整可信claims和`kid`。
- [x] JWKS可用于独立验证Actor Token，且响应不含私钥信息。
- [x] 内部认证缺失/错误不能调用内省；有效、吊销、过期、篡改凭证结果明确且不泄露hash。
- [x] Control System能通过两个真实Adapter构造`InvocationIdentity`，未知`kid`、GenB不可用或身份不一致均拒绝。
- [x] scope契约统一，Short-term Memory三个动作分别按read/write/delete授权。
- [x] GenB与Control System相关测试、构建、秘密扫描和旧SDK扫描通过。
- [x] 审查、报告、索引和两个仓库精确提交完成。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对现有身份实现、设计契约和配置边界 | 已完成 | 已确认HMAC、claims、scope与Control Adapter差距 |
| 2 | RED→GREEN：RS256 Actor Token与JWKS | 已完成 | 通过现有组件会话公开HTTP和JWKS验签 |
| 3 | RED→GREEN：受保护服务凭证内省 | 已完成 | 有效/失效/内部认证矩阵 |
| 4 | RED→GREEN：Control System HTTP/JWKS Adapter及scope统一 | 已完成 | Adapter合同和Interface回归 |
| 5 | 双项目全量回归、安全审查和精确提交 | 已完成 | GenB 108项、Control 21项；提交`ef0a627`/`add0e13` |

### 6. 当前风险

- GenB当前没有租户目录；本轮用服务端`tenant-id`配置提供可信单租户值，不能声称已完成多租户目录集成。
- 本轮支持静态活动密钥和`kid`，但不包含多把并行密钥、自动轮换或已签发Token在线吊销。
- 内省依赖GenB在线可用；Control System必须在网络失败时fail-closed，缓存策略后续单独实现。
- 身份契约门禁已解除，但真实测试智能体、Short-term Memory绑定和A/B逻辑实例隔离演示尚未执行，进入下一Iteration。

## 任务：核心组件平台 Iteration 9——Control System Short-term Memory 纵向切片

### 1. 目标

新建 `control-system-service`，不依赖旧 Runtime SDK，通过真实 HTTP Interface 交付 Short-term Memory 的首条可调用纵向切片：双凭证构造身份、提交回合、准备上下文、幂等、四维隔离和Redis持久化。

### 2. 范围和边界

- 对外Interface：`POST /api/v1/control-system/short-term-memory/turns:commit`、`POST /api/v1/control-system/short-term-memory/context:prepare`、`DELETE /api/v1/control-system/short-term-memory/sessions/{sessionId}`。
- 身份必须由服务凭证内省结果 + 已验签Actor Token共同构造；不信任请求正文中的tenant/user/agent/session。
- 本轮提供可替换存储Port、In-memory Adapter和Redis Adapter；Redis键不包含原始身份。
- 本轮不实现Long-term Memory、摘要模型调用、完整RAG、管理端测试台或生产部署。
- 旧 `bank-agent-runtime` 仅可阅读参考，新服务依赖和源码不得引入它。

### 3. Module与Seam

| Module/Adapter | 职责 |
|---|---|
| `IdentityModule` | 验证服务凭证、RSA Actor Token、agent/component/scope一致性，构造不可变 `InvocationIdentity` |
| `ShortTermMemoryModule` | 拥有commit/prepare/clear唯一业务Interface，处理幂等、窗口、预算和隔离 |
| `SessionStorePort` | Module拥有的存储Seam，不暴露Redis类型 |
| `InMemorySessionStore` | 公开Interface测试和快速回归Adapter |
| `RedisSessionStore` | 本地真实Redis Adapter，负责原子幂等、裁剪、TTL和不可逆键 |
| HTTP Adapter | DTO、Header、RFC 9457错误和Module调用，不承载记忆业务规则 |

### 4. 完成标准

- [x] 缺服务凭证或Actor Token返401，agent不一致、组件或scope不允许返403。
- [x] 同一身份/session提交后可通过prepare获得最近对话，响应包含预算和裁剪元数据。
- [x] 同Idempotency-Key同请求返回原结果且不重复写，同key不同请求明确冲突。
- [x] tenant/user/agent/session任一变化均不能读取原会话，clear只清理当前作用域。
- [x] Redis Adapter通过与In-memory Adapter相同的Port行为测试，原始身份不出现在Redis键中，数据按TTL设置。
- [x] live/ready/version、OpenAPI、README、配置示例和无Runtime SDK依赖检查完整。
- [x] 公开Interface、Identity安全、Adapter合同、真实Redis集成及全量测试通过。
- [x] 审查、报告、索引和精确提交完成。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对专项指南、契约、依赖和本地Redis | 已完成 | Python/FastAPI/Redis/cryptography可用，Redis `PONG` |
| 2 | RED→GREEN：双凭证身份与第一个commit/prepare纵向切片 | 已完成 | 真实HTTP Interface从不存在到可提交/召回 |
| 3 | RED→GREEN：幂等、冲突、预算和四维隔离 | 已完成 | 公开Interface和安全行为测试通过 |
| 4 | 实现Redis Adapter并跑真实本地Redis合同/集成测试 | 已完成 | Lua原子、TTL、HMAC键，测试键残留0 |
| 5 | 补齐健康、OpenAPI、文档、无SDK依赖与全量回归 | 已完成 | 16项测试、compileall、OpenAPI同步和SDK扫描通过 |
| 6 | 审查、记录和精确提交 | 已完成 | 实现提交 `3f7f631`，Iteration报告已入索引 |

### 6. 结果和下一门禁

- `control-system-service` 已具有可运行的Short-term Memory Module、Identity Module与Redis Adapter，无旧Runtime SDK依赖。
- 实现已精确提交为 `3f7f631`；没有提交或覆盖工作区内的其他历史改动。
- 本地Redis DB 15真实验证通过，运行后本轮唯一测试前缀键已精确清理，残留0。
- GenB当前Component Session仍使用派生对称密钥，claims也缺`tenantId/iss/aud/components`，不能与本轮RS256执行面身份直接联调。
- 因此本地启动工厂仅允许`local/test`，`production`会fail-closed；下一Iteration先升级GenB Actor Token/JWKS和服务凭证内省契约，再接真实测试智能体。

## 任务：核心组件平台 Iteration 8——目录加载故障与菜单层级修复

### 1. 目标

修复管理端核心组件目录在实际入口加载失败的问题，并将侧边栏调整为“智能体中心”父菜单，下设“智能体列表”和“核心组件”，保持中英文产物和详情路由一致。

### 2. 已确认根因与范围

- 已确认：用户实际入口是本地 `9100`。客户端 Vite 将 `/genb` 代理到本地管理端，并通过同源存储共享登录态，不涉及公网部署。
- 已确认：客户端登录只写入 `genb-client-token`，核心组件 API 只读取旧键 `token`，所以请求未携带 Bearer Token并返回403。
- 已确认：真实浏览器在仅保留 `genb-client-token` 时可稳定复现目录403和页面失败提示；同一接口显式携带管理员Token时返回200和14条。
- 本次要做：菜单层级和双语文案修复、统一管理端API Token读取规则、回归测试、双语构建、本地9100真实浏览器验收和纠正诊断记录。
- 本次不做：不部署、不修改核心组件数据、不恢复物理外键。

### 3. 完成标准

- [x] “智能体中心”作为父菜单默认展开，子菜单依次为“智能体列表”和“核心组件”。
- [x] 原智能体页面和核心组件目录/详情路由仍可正常进入，面包屑名称正确。
- [x] 仅存在 `genb-client-token` 时，9100核心组件请求携带认证并返回14条。
- [x] 菜单与认证回归测试、中英文构建和本地9100真实浏览器验证通过。
- [x] 纠正此前错误的公网诊断记录，不执行部署。
- [x] 审查、报告和精确提交完成。

### 4. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 建立用户实际入口反馈环并定位403 | 已完成 | 9100真实浏览器仅客户端Token时目录403 |
| 2 | RED→GREEN：菜单父子层级和标题模型 | 已完成 | 自动测试断言固定父子关系 |
| 3 | 修复菜单样式和双语文案 | 已完成 | 中文浏览器与英文构建验证 |
| 4 | RED→GREEN：统一Token读取并回归9100 | 已完成 | 客户端Token场景从403变200/14条 |
| 5 | 双语构建、纠正记录、审查并精确提交 | 已完成 | 构建、报告、源码提交 `6d5f46b` |

### 5. 当前进度

- 进行中：无；本地9100目录403和菜单层级均已修复。
- 已完成：菜单层级、Token统一、双语构建和真实9100浏览器验收。
- 已完成：GenB 源码提交 `0f63ef4`、`6d5f46b`。
- 阻塞：无；本任务不需要部署。

### 6. Iteration 8 第二阶段：详情页真实治理写操作

#### 目标与范围

在现有只读详情快照和既有后端控制面接口之上，提供管理员可操作的完整治理闭环：Implementation注册/启停、配置草稿创建/发布/回滚、智能体绑定/启停；每次成功操作后刷新详情和审计。后端RBAC、状态机和审计继续作为最终门禁。

本阶段不新增数据库表、不创建物理外键、不修改固定五系统/14组件目录、不实现配置删除或历史覆盖、不部署。

#### 页面组件边界

| 组件 | 单一职责 |
|---|---|
| `CoreComponentDetail.vue` | 编排标签页、三个弹窗、确认动作和详情刷新 |
| `CoreComponentImplementationTable.vue` | 展示实现并发出注册/启停事件 |
| `CoreComponentConfigTable.vue` | 展示版本并发出新建/发布/回滚事件 |
| `CoreComponentBindingTable.vue` | 展示绑定并发出绑定/启停事件 |
| `CoreComponentImplementationDialog.vue` | 收集和校验Implementation注册参数 |
| `CoreComponentConfigDialog.vue` | 收集配置草稿、解析JSON与secretRefs |
| `CoreComponentBindingDialog.vue` | 选择真实智能体、Implementation和已发布配置 |
| `useCoreComponentGovernance.js` | 执行写接口、归一错误和管理操作中状态 |
| `governanceFormModel.js` | 纯函数构造配置和绑定选项 |

#### 完成标准

- [x] 管理员可注册HTTP Implementation，并可停用/恢复。
- [x] 管理员可创建配置草稿、发布草稿，并将历史已发布版本回滚为新版本。
- [x] 管理员只能把真实智能体绑定到启用Implementation的已发布配置，并可停用/恢复绑定。
- [x] 所有写操作使用真实后端接口，成功后详情和审计同步刷新；失败展示后端原因。
- [x] JSON配置输入无效、无已发布配置、重复有效绑定等情况被前后端明确拒绝。
- [x] 前端模型测试、后端控制面专项/全量测试、双语构建和本地9100浏览器验收通过。
- [x] 远程核心组件表物理外键仍为0；不删除已有数据。
- [x] 审查、报告和精确提交完成。

#### 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对既有写接口、状态机、DTO和详情读模型 | 已完成 | 七类写动作均已有公开HTTP接口与RBAC |
| 2 | RED→GREEN：表单模型与写API封装 | 已完成 | JSON、secretRefs、绑定候选模型测试通过 |
| 3 | 实现三类表格操作与三个独立弹窗 | 已完成 | props/emits边界和中英文案已构建验证 |
| 4 | 详情页编排、成功刷新、确认和错误反馈 | 已完成 | 真实操作后详情/审计变化已核对 |
| 5 | 后端测试、双语构建、9100浏览器和FK回归 | 已完成 | 专项14/14、全量105/105、双语构建、真实页面与相关表FK=0 |
| 6 | 审查、记录和精确提交 | 已完成 | 报告已写，源码提交 `2d7a4f0` |

#### 实施结果

- 本地 `9100` 页面真实完成 Implementation 注册/停用/恢复、配置草稿/发布/回滚、智能体绑定/停用/恢复。
- 验证数据保留在 `SHORT_TERM_MEMORY`：实现 `iteration8-governance-20260723-v1`，回滚生成的 `iteration8-default` v2，绑定 `agent-sdlc-ai-testing`。
- 最终状态：Implementation `REGISTERED`，v1/v2 均为 `PUBLISHED`，智能体绑定 `ENABLED`，管理审计 9 条。
- 本轮未部署，未删除远程数据，未新增表或物理外键。

## 任务：核心组件平台 Iteration 7——组件详情治理视图

### 1. 目标

让管理员从五系统/14组件目录进入任意固定组件的详情页，通过一个真实后端快照查看该组件的基本信息、Implementation、配置版本、智能体绑定和管理审计，为下一轮可写治理操作建立稳定读模型。

### 2. 范围

本次要做：组件详情聚合 DTO 和只读 API、Repository 查询、公开 HTTP 集成测试、卡片进入详情路由、详情 composable、概览头部、实现/配置/绑定/审计四类数据表、中英文文案、加载/空状态/失败重试、真实浏览器验收。

本次不做：实现注册表单、配置发布/回滚操作、绑定启停操作、服务凭证页面、长短记忆执行服务、数据库新表、远程核心组件治理数据写入和部署。真实登录验收仍会产生正常登录审计。

### 3. 数据库约束

- 本轮不新增表和字段。
- 所有读取使用现有逻辑关联，不创建或恢复任何物理外键。
- 远程 7 张核心组件控制面表的物理外键数量必须保持为 0。

### 4. 页面组件边界

| 组件 | 单一职责 |
|---|---|
| `views/core-components/Detail.vue` | 路由参数和详情容器组合 |
| `CoreComponentDetail.vue` | 编排加载、错误和标签页 |
| `CoreComponentDetailHeader.vue` | 展示组件身份、状态并发出返回/刷新事件 |
| `CoreComponentImplementationTable.vue` | 展示实现列表 |
| `CoreComponentConfigTable.vue` | 展示配置版本列表，不展示配置秘密 |
| `CoreComponentBindingTable.vue` | 展示智能体绑定列表 |
| `CoreComponentAuditTable.vue` | 展示最近管理审计 |
| `useCoreComponentDetail.js` | 请求详情快照并管理只读状态 |

### 5. 完成标准

- [x] 管理员点击任意组件卡片可进入稳定详情 URL。
- [x] 后端详情接口一次返回目录信息、实现、配置、绑定和最近审计。
- [x] 组件不存在、未认证、缺少 `component.read` 权限时由后端拒绝。
- [x] 空实现/配置/绑定/审计展示真实空状态，不伪造数据。
- [x] 页面只展示配置版本元数据，不泄露配置正文和 secret。
- [x] 中文、英文页面名称与固定文案正确。
- [x] 后端专项/全量测试、前端逻辑测试和双语构建通过。
- [x] 浏览器从目录卡片进入详情并返回目录的链路通过。
- [x] 远程核心组件表物理外键仍为 0。
- [x] 审查、报告、索引和精确提交完成。

### 6. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 定义详情读模型、任务和组件边界 | 已完成 | 聚合接口和七个页面组件职责明确 |
| 2 | RED→GREEN：详情公开 HTTP 接口 | 已完成 | 3 项公开 HTTP 测试通过 |
| 3 | 开发详情路由和只读治理页面 | 已完成 | 卡片进入、四标签页和空状态完成 |
| 4 | 双语构建、浏览器和后端全量回归 | 已完成 | 双语构建、105项测试、浏览器链路、FK=0 |
| 5 | 审查、记录和精确提交 | 已完成 | GenB 提交 `bb0d406`，未混入生成物 |

### 7. 当前进度

- 进行中：无；Iteration 7 已完成。
- 已完成：真实后端详情响应只包含 `component/implementations/configVersions/bindings/audits`，不包含配置正文和 secretRef。
- 已完成：本地后端已重启并健康，真实浏览器目录→详情→目录链路通过。
- 已完成：GenB 源码提交 `bb0d406`。
- 阻塞：无。

## 任务：核心组件平台 Iteration 6——管理端目录页与无物理外键数据库门禁

### 1. 目标

在既有 GenB 控制面 API 之上交付第一版核心组件管理端：管理员可以按五大系统查看固定 14 个核心组件，按名称、编码、系统和交付状态筛选，并明确区分已开发、开发中和规划中组件。同时把“领域设计允许外键关系、实际建表不创建物理外键”落实为可测试的 JPA/DDL 门禁。

### 2. 范围

本次要做：核心组件菜单和路由、目录 API 封装、目录状态 composable、筛选栏、五系统分组和组件卡片、中英文文案、加载/空状态/错误重试、H2 无物理外键测试、JPA 禁止生成外键、远程既有外键兼容迁移脚本、任务与报告记录。

本次不做：组件详情治理表单、服务凭证页面、独立测试台、短期/长期记忆执行服务、远程数据删除、生产部署。

### 3. 数据库硬性约束

- 设计文档和 ER 图可以表达逻辑外键关系。
- PostgreSQL、H2 和后续其他数据库的实际 DDL 不得创建 `FOREIGN KEY` 约束。
- 关联完整性由服务层校验、事务、唯一约束和必要索引保证。
- 远程库现有物理外键只能通过可审计迁移删除；迁移前后核对表、行数和约束，不删除业务数据。
- 不使用 Hibernate `ddl-auto:update` 作为正式发布迁移方案。

### 4. 完成标准

- [x] 管理端出现“核心组件”菜单并可进入目录页。
- [x] 页面从 `/v1/core-components` 读取真实五系统/14组件目录。
- [x] 搜索、系统筛选、状态筛选、重置和刷新行为可用。
- [x] 中文产物显示中文名称，英文产物显示英文名称。
- [x] 加载失败可见且可重试；空结果不会伪造组件数据。
- [x] JPA 测试生成的核心组件表不存在物理外键。
- [x] 提供远程既有外键的无数据删除迁移脚本和验证查询。
- [x] 管理端中英文构建、后端专项/全量测试通过。
- [x] 代码审查、报告、索引和精确提交完成。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对现有控制面、管理端结构和远程约束 | 已完成 | 远程已有 7 表、5系统/14组件及 6 个自动生成外键 |
| 2 | 写入无物理外键规则并建立失败测试 | 已完成 | 测试先发现外键，修复后 7 表无 imported key |
| 3 | 禁止 JPA 生成外键并准备兼容迁移 | 已完成 | 远程删除 6 个外键，迁移前后行数一致 |
| 4 | 开发核心组件目录页 | 已完成 | 本地真实 API、筛选、重置和浏览器错误检查通过 |
| 5 | 中英文构建和后端全量测试 | 已完成 | 双语构建通过，后端 102 项通过 |
| 6 | 审查、报告、索引和精确提交 | 已完成 | GenB 提交 `d6df8c0`，未混入 target、.vite、dist |

### 6. 当前进度

- 进行中：无；Iteration 6 已完成。
- 已完成：远程 6 个物理外键已在行数保护事务中删除，7 表数据行数未变化，最终物理外键数为 0。
- 已完成：核心组件目录页真实展示五系统/14组件，双语构建和浏览器验收通过。
- 已完成：GenB 源码提交 `d6df8c0`。
- 阻塞：无。

## 任务：核心组件平台 Iteration 5——服务凭证与短时组件会话

### 1. 目标

让管理员为逻辑智能体签发只显示一次、仅保存强哈希、可过期和可吊销的服务凭证；已获智能体使用权的登录用户可用该凭证换取包含有效绑定、scope和配置快照的短时组件会话。

### 2. 范围

本次要做：凭证签发/元数据查询/吊销、短时组件会话、JWT用途隔离、scope和绑定快照、管理审计、真实登录/JWT/H2公开HTTP测试。

本次不做：不实现凭证轮换宽限期；不开发Vue页面；不连接远程数据库；不部署；组件数据面不回调GenB做逐请求鉴权。

### 3. 完成标准

- [x] 凭证secret只在签发响应出现一次，数据库只保存bcrypt哈希。
- [x] 凭证可配置过期时间并可立即吊销，过期/吊销/篡改凭证不能换取会话。
- [x] 只有有权使用该智能体的登录Actor可申请组件会话。
- [x] 组件会话只包含已请求、已绑定、已启用且scope允许的组件。
- [x] Actor Token包含用途、Actor、agent、session、scope、绑定快照、jti和短时过期时间。
- [x] 组件Actor Token不能冒充GenB登录Token访问管理端。
- [x] 全量测试、敏感信息检查、记录和精确提交完成。

### 4. 当前进度

- 进行中：无；Iteration 5已完成。
- 已完成：公开HTTP安全行为、GenB后端101项全量测试、代码提交`007b7b2`、记录提交`c170e0c`；本地后端已恢复。
- 阻塞：无。

## 任务：核心组件平台 Iteration 4——GenB 治理闭环

### 1. 目标

在 Iteration 3 控制面最小闭环之上，补齐可安全运维的生命周期：Implementation 启停、配置版本查询与回滚、绑定停用与恢复，以及不记录配置正文和敏感信息的管理审计。

### 2. 范围

本次要做：公开 HTTP Interface、后端 RBAC、JPA 状态机与审计实体、H2 集成测试、计划和阶段报告。

本次不做：不开发 Vue 页面；不签发服务凭证或组件会话；不连接远程 PostgreSQL/Redis；不部署；不提交 `target`、Vite 缓存或构建产物。

### 3. 完成标准

- [x] 管理员可停用/恢复已注册 Implementation，停用期间禁止新增绑定。
- [x] 管理员可查询配置版本，并将历史已发布版本回滚为新的不可变已发布版本。
- [x] 管理员可停用/恢复智能体绑定，生效解析只返回启用绑定。
- [x] 所有成功管理变更可按组件查询审计，审计不包含配置正文、密码或 secret 值。
- [x] 未认证或缺少权限的请求仍由后端拒绝。
- [x] 全量 Maven 测试通过，源码和记录精确提交。

### 4. 当前进度

- 进行中：无；Iteration 4已完成。
- 已完成：四组公开HTTP行为、GenB后端93项全量测试、代码提交`07fc129`、记录提交`b889e79`，本地8581后端已恢复且健康为`UP`。
- 阻塞：无。

## 任务：核心组件平台Iteration 3——GenB控制面最小闭环

### 1. 背景

Runtime System的Fake与Direct Provider离线主链路已经完成。用户确认进入M3，需要在GenB建立固定五系统/14组件目录、实现注册、配置发布、智能体绑定和后端RBAC，为Runtime与Control System接入提供控制面。

### 2. 目标

通过真实GenB用户登录和JWT，从固定目录查询开始，完成`组件目录→实现注册→配置草稿/发布→智能体绑定→生效解析`最小闭环，并确保未认证、无权限、未发布配置和重复有效绑定被拒绝。

### 3. 范围

本次要做：JPA实体与约束、五系统/14组件幂等种子、控制面Java Module、管理Interface、`component.read/configure/bind`权限、H2公开HTTP集成测试、文档和报告。

本次不做：不开发Vue页面；不签发服务凭证/组件会话；不调用Runtime System；不修改远程数据库；不部署；不提交`target`、Vite缓存或构建产物。

### 4. 完成标准

- [x] 管理员登录后可查询固定五系统/14组件目录。
- [x] 核心系统和核心组件不能通过页面或通用接口新增。
- [x] 管理员可为固定组件注册Implementation。
- [x] 配置草稿可发布为不可变版本。
- [x] 只能把存在的智能体绑定到已发布配置。
- [x] 同一智能体和组件最多一个有效主绑定。
- [x] 未认证或缺少权限的调用被后端拒绝。
- [x] H2集成测试、编译和安全检查通过。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对GenB数据、权限和测试结构 | 已完成 | 源码无业务脏改动，H2可用于测试 |
| 2 | RED→GREEN：JWT查询固定目录 | 已完成 | 真实登录和HTTP集成测试 |
| 3 | RED→GREEN：Implementation注册 | 已完成 | 固定componentCode与唯一约束 |
| 4 | RED→GREEN：配置草稿与发布 | 已完成 | 状态机和不可变性 |
| 5 | RED→GREEN：智能体绑定与解析 | 已完成 | 已发布校验和唯一有效绑定 |
| 6 | RBAC、文档、报告和全量验证 | 已完成 | 89项Maven测试全部通过 |
| 7 | 精确提交GenB源码和记录 | 已完成 | GenB`0c4759a`；记录`a2019b0` |

### 6. 当前进度

- 进行中：无；M3最小控制面闭环已完成并提交。
- 已完成：M1提交`c0610cb`、M2离线工程提交`10d5b1e`。
- 阻塞：无；凭证/组件会话和远程数据库迁移不在当前Iteration 3范围。

### 7. 风险和遗留问题

当前生产配置依赖Hibernate `ddl-auto:update`且源码配置含既有敏感值，M3不会把测试直接指向远程库。生产迁移脚本、秘密外置和组件会话属于后续门禁。

## 任务：核心组件平台Iteration 2——可配置Direct Provider主链路

### 1. 背景

Iteration 1已建立统一Inference Interface和Fake Provider纵向切片。用户确认继续开发，下一步进入M2，在不写入真实密钥、不产生付费调用的前提下，实现可配置的模型路由与Direct Provider Adapter。

### 2. 目标

保持调用方Interface不变，通过版本化路由配置将逻辑模型别名解析到OpenAI-compatible Direct Provider；统一普通推理、结构化输出、Embedding、模型目录、健康和Provider错误，为后续真实凭证联调建立可验证主链路。

### 3. 范围

本次要做：路由配置Module、环境变量Secret Resolver、OpenAI-compatible Direct Provider Adapter、外部HTTP传输Seam、错误归一、动态模型目录、配置示例、公开Interface测试、文档和阶段报告。

本次不做：不写或申请真实API Key；不发起真实外部调用；不完成费用/地域/数据政策签字；不实现GenB控制面、Control System、重试/熔断和生产部署。

### 4. 完成标准

- [x] 有效配置可将逻辑别名路由到Direct Provider。
- [x] 配置不存在、重复别名、能力不匹配或secretRef非法时明确失败。
- [x] Provider普通推理和Embedding响应归一到既有Interface。
- [x] Provider 4xx、429、5xx、超时和非法响应映射为统一Problem Details。
- [x] `/models`与健康接口来自已发布路由而非硬编码目录。
- [x] 测试仅替换真实外部HTTP传输，不访问网络、不包含秘密。
- [x] 全量测试、编译、配置和安全检查通过。
- [x] 精确提交本任务文件，不混入既有工作区改动。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 固化M2 Iteration 2范围和公开行为 | 已完成 | 继续使用既有Inference Interface |
| 2 | RED→GREEN：配置路由普通推理 | 已完成 | 公开HTTP Interface调用外部Mock Transport |
| 3 | RED→GREEN：配置拒绝和错误归一 | 已完成 | Problem Details和启动失败测试 |
| 4 | RED→GREEN：Embedding与模型目录 | 已完成 | 数量/维度/目录测试 |
| 5 | 健康、配置示例、README和报告 | 已完成 | 静态检查与文档复核 |
| 6 | 全量验证、安全检查和精确提交 | 已完成 | 32项pytest、compile、启动和secret扫描通过；提交`10d5b1e` |

### 6. 当前进度

- 进行中：无；Iteration 2离线工程主链路已完成并提交。
- 已完成：Direct Provider、配置路由、结构化输出、SSE、Embedding、动态模型目录、错误归一、32项测试和实际启动验证。
- 阻塞：真实Provider选型、密钥和合规证据尚未提供，但不阻塞离线契约实现。

### 7. 风险和遗留问题

本迭代只能证明兼容协议、配置和错误语义；在真实Provider官方契约、脱敏调用、费用与数据政策门禁通过前，不能宣称M2完整验收或用于生产。

## 任务：为英文统一登录增加无目录短入口

### 1. 背景

中文版统一登录使用 `/portal/login`，英文版当前使用 `/genb-client-en/portal/login`。用户要求先将英文访问地址调整为 `/portal/login?lang=en`，查看实际效果。

### 2. 目标

仅修改前端服务器 Nginx 精确入口：无 `lang=en` 时继续返回中文客户端入口，有 `lang=en` 时返回英文客户端入口；保留现有中英文静态资源、API 和兼容入口。

### 3. 范围

本次要做：备份并精确修改 `/etc/nginx/conf.d/alaya-to.conf`，执行 `nginx -t`、reload 和中英文 HTTP 验证，记录部署与回滚点。

本次不做：不修改前端源码和构建产物；不删除 `/genb-client-en/` 静态资源/API 路由；不修改后端、数据库、管理端和其他系统入口。

### 4. 完成标准

- [x] `/portal/login` 返回中文客户端入口。
- [x] `/portal/login?lang=en` 返回英文客户端入口。
- [x] 两个入口的主静态资源可加载。
- [x] 原中英文兼容入口和 API 保持可用。
- [x] `nginx -t` 通过并完成 reload。
- [x] 已记录配置备份、验证结果和回滚方式。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对服务器当前精确入口配置 | 已完成 | 只读输出目标 location |
| 2 | 备份并修改 Nginx 配置 | 已完成 | 备份存在、diff 仅影响目标入口 |
| 3 | 检查并 reload Nginx | 已完成 | `nginx -t` 与 reload 成功 |
| 4 | 验证中英文入口和回归路径 | 已完成 | HTTP、HTML 和静态资源检查 |
| 5 | 写部署记录并更新索引 | 已完成 | `records/deployments/` 与索引可追溯 |

### 6. 当前进度

- 进行中：无，Nginx 修改和 HTTP 回归已完成，等待用户查看最终视觉效果。
- 已完成：配置备份、精确入口修改、`nginx -t`、reload、中英文入口/资源/API/管理端回归和记录。
- 阻塞：无；Chrome CDP 尚未获远程调试授权，因此最终视觉效果由用户直接查看。

### 7. 验收记录

- [x] Nginx 配置检查
- [x] 中文入口
- [x] 英文入口
- [x] 静态资源和 API 回归
- [x] 回滚点

### 8. 风险和遗留问题

英文页面的公开入口隐藏 `genb-client-en`，但英文静态资源和 API 仍保留该内部前缀。本轮不做全路径迁移，以控制对既有部署的影响。

## 任务：核心组件平台Iteration 1——最小Inference Engine Fake纵向切片

### 1. 背景

设计、平台总纲、Runtime Inference专项和Control记忆专项已经明确。用户授权制定详细任务计划并开始开发。根工作区存在大量既有未提交/未跟踪资料和子仓库改动，本任务必须建立独立服务目录并精确控制提交范围。

### 2. 目标

完成核心组件平台详细实施计划，并以TDD建立`runtime-system-service`第一条可运行纵向切片：有权调用方通过统一Inference Interface调用Fake Provider，获得标准响应；随后增量覆盖结构化输出、Embedding、模型列表、健康和基础流式Interface。

### 3. 范围

本次要做：计划、Python工程骨架、应用工厂、身份Port、Inference深Module、Fake Provider Adapter、公开HTTP Interface、OpenAPI、配置、README、测试和阶段报告。

本次不做：不调用真实付费Provider；不写任何真实secret；不修改GenB数据库/Java/Vue；不实现Control System；不安装依赖；不部署。

### 4. 完成标准

- [x] 新服务可在已有Python环境启动。
- [x] 未认证/无scope请求被拒绝。
- [x] 非流式Inference通过Fake Adapter返回统一信封。
- [x] 结构化JSON按Schema校验，非法结果返回统一错误。
- [x] Embedding数量、顺序、维度和有限值校验。
- [x] models、live、ready、内部模型健康和基础SSE流式Interface可用。
- [x] 测试只通过公开Interface验证行为，不依赖内部Implementation。
- [x] README、OpenAPI、环境示例和报告完成。
- [x] 无旧Runtime SDK依赖、无秘密、无网络调用。
- [x] 精确暂存并提交本任务文件，不混入既有改动。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 编写全项目详细实施计划 | 已完成 | `records/plans/20260723-PLAN-core-component-platform-implementation.md` |
| 2 | RED→GREEN：普通Inference纵向切片 | 已完成 | 公开Interface测试通过 |
| 3 | RED→GREEN：身份和scope | 已完成 | 401/403 Problem Details通过 |
| 4 | RED→GREEN：结构化输出 | 已完成 | 合法/非法JSON Schema测试通过 |
| 5 | RED→GREEN：Embedding | 已完成 | 正常/维度/非法数值测试通过 |
| 6 | RED→GREEN：models/health/stream | 已完成 | Interface和SSE测试通过 |
| 7 | OpenAPI、配置、README和报告 | 已完成 | JSON解析、运行时路径和文档检查通过 |
| 8 | 全量测试、安全检查和精确提交 | 已完成 | 15项pytest、compile、secret/network扫描通过；提交`c0610cb` |

### 6. 当前进度

- 进行中：无；Iteration 1开发基线已完成并提交。
- 已完成：详细计划、20个服务文件、15项测试、实际端口健康、OpenAPI/配置/安全检查和报告。
- 阻塞：无；本机使用已有GenO Python 3.12虚拟环境运行测试，不修改或安装其中依赖。

### 7. 验收记录

- [x] Tracer bullet
- [x] 身份/scope
- [x] 结构化输出
- [x] Embedding
- [x] models/health/stream
- [x] 文档和OpenAPI
- [x] 全量验证和提交

### 8. 风险和遗留问题

Direct Provider、数据合规和生产技术栈仍属于M2门禁。本迭代只建立可替换Seam和Fake Adapter，不能把Fake结果当作一期最终模型能力验收。

## 任务：将自建Inference Engine纳入核心组件一期设计与开发

### 1. 背景

Alaya Model Gateway当前存在Zhipu依赖不可用、Embedding路径与字段不一致等问题，不能作为长短记忆一期的唯一必选模型依赖。用户确认由项目自建统一模型调用层，并写入设计与开发文档。

### 2. 目标

将`Runtime System / Inference Engine Service`的最小能力提前到一期基础设施阶段，由它统一提供对话、结构化输出、流式和Embedding Interface；Control System和智能体只依赖该Interface，Alaya降为可选Adapter。

### 3. 范围

本次要做：更新总体设计、平台开发总纲、Control System长短记忆专项；明确Module/Interface/Adapter、GenB管理边界、凭证归属、一期工作包、测试、降级、部署和验收；新增ADR和报告并更新索引。

本次不做：不实现模型调用服务代码；不申请或写入模型厂商凭证；不安装依赖；不调用真实付费模型；不部署服务。

### 4. 完成标准

- [x] 总体设计明确Inference Engine最小能力是一期开工依赖。
- [x] Control System不直接依赖Alaya或模型厂商协议。
- [x] 统一模型Interface覆盖非流式、流式、Embedding、模型能力和健康。
- [x] Direct Provider、Alaya和Fake Adapter边界明确。
- [x] GenB、Runtime System、Control System和智能体的模型职责不重叠。
- [x] 凭证、配额、超时、路由、降级、观测和验收可实施。
- [x] ADR、术语、索引、报告和静态校验完成。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对现有模型与一期章节 | 已完成 | 列出并清除所有强依赖Alaya的表述 |
| 2 | 更新总体设计 | 已完成 | 范围、架构、调用、验收一致 |
| 3 | 更新平台总纲和两个专项 | 已完成 | 新增Inference Engine专项，Interface、代码结构和工作包可执行 |
| 4 | 新增ADR、术语和报告 | 已完成 | 决策可追溯 |
| 5 | 完整性与安全校验 | 已完成 | 示例、链接、秘密和格式检查通过 |

### 6. 当前进度

- 进行中：无，文档设计阶段完成，等待Provider和技术栈启动门禁确认。
- 已完成：总体设计、平台总纲、Runtime Inference专项、Control记忆专项、ADR、术语、索引、报告和静态校验。
- 阻塞：真实Provider、凭证、Embedding模型和外部数据合规仍需编码启动门禁确认。

### 7. 验收记录

- [x] 总体设计
- [x] 平台开发总纲
- [x] Runtime Inference专项
- [x] 长短记忆专项
- [x] ADR和术语
- [x] 索引、报告和校验

### 8. 风险和遗留问题

自建范围必须控制在深Inference Engine Module：统一调用、路由、错误、用量和Adapter；不在一期扩张为模型训练、复杂计费或全功能模型运营平台。

## 任务：编写核心组件平台全栈开发总纲

### 1. 背景

现有《Control System长短记忆一期开发指南》只覆盖一期专项，不能替代整个核心组件平台的开发总纲。完整范围应同时包含GenB管理控制面、五大系统与14个核心组件执行面，以及智能体接入和编排面。

### 2. 目标

编写一份可直接指导多人分工实施的全栈开发总纲，明确GenB如何注册、配置、绑定和治理组件，各系统服务如何实现并暴露组件Interface，智能体如何获得授权、解析端点并调用组件，以及14个组件如何完成全量验收。

### 3. 范围

本次要做：总体工程拓扑、三面架构、领域模型、统一注册清单、GenB控制面、五个系统服务、14个组件基线Interface、智能体接入、身份鉴权、配置、数据归属、可观测、测试、部署、版本兼容、团队分工和全量验收。

本次不做：不创建实际服务代码；不执行数据库迁移；不安装依赖；不启动或部署服务；不修改现有Runtime SDK。

### 4. 完成标准

- [x] 文档完整覆盖GenB、五个系统服务、14个核心组件和智能体。
- [x] 给出“注册—绑定—授权—解析—调用—审计”的端到端契约。
- [x] 明确现有Runtime SDK只作参考，公共契约包不演变为新的重型SDK。
- [x] 每个核心组件都有职责、最小Interface、数据归属、权限和验收基线。
- [x] 现有长短记忆指南明确成为Control System一期专项子文档。
- [x] 架构决策、术语、索引、报告和文档状态同步更新。
- [x] 链接、组件数量、代码示例和验收矩阵通过静态校验。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 核对已有总体设计和一期专项文档 | 已完成 | 范围差异清单 |
| 2 | 编写核心组件平台全栈开发总纲 | 已完成 | 覆盖三面、五系统、14组件 |
| 3 | 补充架构决策和术语 | 已完成 | ADR与术语一致 |
| 4 | 更新文档上下位关系、索引和报告 | 已完成 | 可从项目索引导航 |
| 5 | 运行完整性和一致性校验 | 已完成 | 数量、链接、示例、敏感信息检查 |

### 6. 当前进度

- 进行中：无，平台级开发文档阶段完成，等待编码启动门禁评审。
- 已完成：平台全栈开发总纲、三面架构ADR、五大系统/14组件开发基线、智能体接入、Control System长短记忆一期专项、索引和静态校验。
- 阻塞：无；未定技术选型会作为编码启动门禁记录，不冒充已批准事实。

### 7. 验收记录

- [x] 平台全景和工程边界
- [x] GenB控制面
- [x] 五个系统和14组件
- [x] 智能体接入与跨系统编排
- [x] 全量验收与交付门禁

### 8. 风险和遗留问题

总纲会定义稳定边界和基准实现，但不会强制“一组件一服务”；每个系统先作为一个可部署服务、内部按深Module隔离，只有出现独立伸缩、独立故障域、技术栈或团队发布节奏的真实证据时才拆服务。

## 任务：编写Control System长短记忆最详细开发实施文档

### 1. 背景

总体设计和一期范围已经明确，但开发人员仍需要一份能直接映射到仓库、文件、Module、Interface、迁移、权限、测试和部署的实施文档。同时要求该文档能够作为其他四个系统后续开发时复用的标准模板。

### 2. 目标

基于五大系统/14组件总体设计，编写一期`control-system-service`、GenB控制面、管理端和测试智能体的详细开发指南，并提供可复制的核心系统开发模板。

### 3. 范围

本次要做：技术基线、仓库和目录、依赖规则、Module/Interface、OpenAPI、身份鉴权、数据模型、Redis、迁移、后端、前端、测试智能体、模型Adapter、异步任务、测试、联调、部署、可观测、安全、回滚、代码评审和完成标准。

本次不做：不创建实际服务代码；不执行数据库迁移；不安装依赖；不启动或部署服务；不改变现有Runtime SDK。

### 4. 完成标准

- [x] 开发人员能够根据文档创建代码骨架并按顺序实施。
- [x] 长短记忆分别具有稳定Interface、文件归属和测试表面。
- [x] GenB控制面、Control System Service和测试智能体的联调契约明确。
- [x] 数据迁移、权限、凭证、Actor身份和敏感信息方案可实施。
- [x] 包含单元、契约、集成、E2E、安全、性能和故障测试清单。
- [x] 包含可供其他系统复制的标准开发文档模板。
- [x] 更新文档索引和历史报告。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 调研并选择开发文档模板 | 已完成 | OpenAPI、RFC 9457、FastAPI、Twelve-Factor、KEP、Google SRE官方资料 |
| 2 | 固化一期开发架构和仓库结构 | 已完成 | 与总体设计和有效ADR一致 |
| 3 | 编写详细开发实施文档 | 已完成 | 覆盖代码、数据、接口、权限、测试和部署 |
| 4 | 补充可复用系统开发模板 | 已完成 | 可替换系统/组件占位符后复用 |
| 5 | 完整性、安全和索引检查 | 已完成 | 示例可解析、无秘密、索引可导航 |

### 6. 当前进度

- 进行中：无，开发文档阶段完成，等待编码启动门禁确认。
- 已完成：需求边界、总体设计、有效ADR、模板调研、2200余行开发实施指南、复用模板、验证、报告和索引。
- 阻塞：无；技术栈按设计建议给出“基准实现”，进入编码前仍需负责人确认。

### 7. 验收记录

- [x] 总体设计和一期范围已确认
- [x] 现有Runtime SDK只参考、不使用
- [x] Memory Runtime Service层已删除
- [x] 开发文档和复用模板完成

### 8. 风险和遗留问题

开发文档可以给出完整基准，但不会把尚未批准的技术栈和仓库选择伪装成既成事实；实现启动门禁中会要求确认`control-system-service`的语言、仓库、数据库schema和生产Redis方案。

## 任务：拉取并审查 GenB 单源码中英文双构建代码

### 1. 背景

同事提出只维护一套管理端源码，构建时分别生成中文 `/genb/` 与英文 `/genb-en/` 两套产物，后端保持不变；同时提供了英文 Nginx location 和手工部署步骤，需要拉取最新 `create-genB` 并核对实现是否安全、完整。

### 2. 目标

保护当前未提交的 GenC 角色权限代码，安全同步公司最新代码；审查双构建、默认语言、资源路径、API 前缀和 Nginx 方案，并通过自动化构建与产物检查验证结论。

### 3. 范围

本次要做：fetch/安全快进最新 `create-genB`；检查与现有脏文件重叠；审查同事提交；分别构建中英文产物；检查资源、Router、语言和 API 路径；复核 Nginx 配置与部署步骤。

本次不做：不覆盖或清理现有未提交代码和生成物；不修改服务器；不 reload Nginx；不部署产物；不提交或推送。

### 4. 完成标准

- [x] 最新公司代码已安全同步，现有未提交修改完整保留。
- [x] 已明确同事提交及修改文件范围。
- [x] 中文产物只使用 `/genb/`，英文产物只使用 `/genb-en/`。
- [ ] 两套产物继续使用同一后端 API，但客户端默认语言仍会被共享 `localStorage` 覆盖。
- [ ] 四项构建和客户端 22 项测试通过；深链接浏览器验收待修复审查问题后执行。
- [x] Nginx 方案、执行顺序和风险有明确审查结论。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | fetch 并核对本地/远端/脏文件 | 已完成 | 本地落后 1 个提交，远端文件与脏文件无重叠 |
| 2 | 安全快进最新代码 | 已完成 | `create-genB` 快进到 `6a145f1`，既存修改完整保留 |
| 3 | 审查双构建和语言实现 | 已完成 | 确认双 base/API 正确，并发现中文视觉污染、客户端存储覆盖等问题 |
| 4 | 运行中英文构建与产物检查 | 已完成 | 四项构建、客户端 22 项测试、HTML/JS 路径检查完成 |
| 5 | 复核 Nginx 与部署步骤 | 已完成 | location 方向正确；sed 行号、固定备份和生效顺序需修正 |
| 6 | 更新报告和索引 | 已完成 | `records/reports/20260722-REPORT-genb-bilingual-build-code-review.md` |

### 6. 当前进度

- 进行中：无；等待同事修正审查问题后复验。
- 已完成：安全拉取、提交审查、四项构建、客户端测试、产物路径/API 检查和 Nginx 步骤审查。
- 阻塞：当前提交存在中文构建包含英文门户视觉、客户端语言存储覆盖、无效声明文件和缺失 `cross-env` 等问题，不建议直接部署。

### 7. 验收记录

- [x] Git 同步
- [x] 未提交修改保护
- [x] 中文构建
- [x] 英文构建
- [ ] 默认语言与存储隔离
- [x] API 前缀
- [x] Nginx 方案

测试结果：管理端 `build:zh`、`build:en` 通过；客户端 `build:zh`、`build:en` 通过；客户端 Vitest 8 个文件 22 项通过。管理端中文 HTML 引用 `/genb/static/`，英文 HTML 引用 `/genb-en/static/`，两套 bundle 均使用 `/genb/api/v1`。英文 HTML 的 `lang` 和标题仍为中文；客户端中英文产物均包含英文 Logo/标语；`global.d.js` 语法检查失败；客户端静态开发脚本引用未安装的 `cross-env`。

### 8. 风险和遗留问题

当前工作区存在未提交的 GenC 角色权限功能和大量构建缓存；如果最新提交修改同一文件，必须停止快进并先确定安全合并方式，不能 stash、reset 或强行覆盖。

## 任务：诊断 GenB 中英文双版本 Nginx 路由

### 1. 背景

服务器新增英文测试部署目录 `/ayala/genb-en/`；老板要求中文公开入口固定为 `http://16.162.33.130/genb`，英文公开入口固定为 `http://16.162.33.130/genb-en`。当前 Nginx 路由存在异常，需要确认实际表现、配置归属和中英文版本边界。

### 2. 目标

在不修改服务器的前提下，查清中文旧版本与英文测试版本的访问地址、静态资源、前端路由和 API 转发是否互相干扰，并给出准确原因与最小修正建议。

### 3. 范围

本次要做：核对本地 Git 与既有改动；检查公开入口实际响应；只读检查服务器 Nginx 配置、部署目录和日志；对比中文旧版本与英文测试版本的前端构建基路径和接口前缀。

本次不做：不修改或重载 Nginx，不替换前端产物，不重启服务，不修改数据库，不提交或推送代码。

### 4. 完成标准

- [x] 中文旧版本的正式入口和当前行为已确认。
- [x] `/ayala/genb-en/` 的异常现象可以稳定复现。
- [x] 已明确问题同时涉及 Nginx 未重载、公开 URL 混淆和英文构建基路径错误。
- [x] 已确认中英文部署目录相互独立，但英文产物当前错误引用中文静态资源前缀。
- [x] 已给出可回滚的最小修正建议，等待用户确认后再实施。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对本地工作区和已有部署记录 | 已完成 | `create-genB`、既存权限代码/生成物和部署事实已核对 |
| 2 | 复现中英文入口行为 | 已完成 | 中文 200；`/ayala/genb-en/` 301 到中文；`/genb-en/` 落入旧根站点 |
| 3 | 只读核对服务器 Nginx 与部署目录 | 已完成 | 新配置晚于当前 worker，尚未 reload；两个部署目录独立存在 |
| 4 | 对比英文构建配置和中文旧版本边界 | 已完成 | 英文 `index.html` 仍引用 `/genb/static/`，英文主 JS 在中文目录 404 |
| 5 | 输出根因与最小修正建议 | 已完成 | 先重构英文 base 并重新构建，再备份、替换、`nginx -t`、reload 和验收 |

### 6. 当前进度

- 进行中：无；诊断完成，等待用户确认是否实施修正。
- 已完成：公开入口复现、服务器配置/目录/日志只读核对、构建基路径检查和最小修正顺序；用户已确认中文 `/genb`、英文 `/genb-en`。
- 阻塞：无。

### 7. 验收记录

- [x] 中文入口
- [x] 英文测试入口
- [x] 静态资源
- [x] 前端路由基路径
- [x] API 前缀边界
- [x] Nginx 配置

测试结果：目标公开地址已确认为中文 `http://16.162.33.130/genb`、英文 `http://16.162.33.130/genb-en`。中文 `/genb/` 返回当前管理端；`/ayala/genb-en/` 被兼容规则 301 到 `/genb/`；由于 07:57 UTC 写入的新 location 晚于 07:27 UTC 的当前 Nginx worker，`/genb-en/` 仍由根站点返回旧页面。英文目录已部署，但 `index.html` 和主 bundle 仍使用 `/genb/` base，主 JS 请求命中中文目录并返回 404。`nginx -t` 通过，本轮未 reload、未替换产物、未修改服务器。

### 8. 风险和遗留问题

中文旧版本和英文测试版本已经使用不同部署目录，但英文构建必须改为 `/genb-en/` base；只 reload 当前配置仍会得到资源 404。实施时应先重建英文产物，再备份配置和英文目录，最后执行配置检查、reload 和中英文双版本回归。

## 任务：设计 GenB 五大系统与14个核心组件总体目标及一期记忆组件

### 1. 背景

需求方提供《第十五章：五大系统与14个核心组件》和管理端菜单示意，希望在“智能体中心”下增加“核心组件”。经讨论确认：五大系统是一级分组，14 项是固定核心能力；一期先建设控制系统中的“短期记忆/工作台”和“长期记忆/知识库”，既能在独立测试台演示，也能绑定智能体后通过 API 调用。

### 2. 目标

形成一份同时包含“五大系统、14个组件总体验收目标”和“一期长短记忆实施细化”的可评审设计文档，并记录关键架构决策。

### 3. 范围

本次设计：领域模型、控制面/数据面边界、模块与服务边界、短期/长期记忆行为、智能体绑定与测试台、API、数据模型、TTL、LLM 接入、凭证、RBAC、审计、部署、可观测性、测试、上线回滚和验收标准。

本次不做：不开发页面和服务；不部署；不建设完整 RAG 知识库；不启用向量检索；不修改 Runtime/CLI。现有 SDK 只作为行为和代码参考，未来可抽取轻量客户端。

### 4. 完成标准

- [x] 明确五大系统与固定 14 个核心组件的层级。
- [x] 明确一期范围为短期记忆和用户长期记忆，不包含完整 RAG。
- [x] 明确Control System直接提供两个记忆组件Interface，部署为`control-system-service`，不设置Memory Runtime Service层。
- [x] 明确五大系统和 14 张组件卡全部展示，其他 12 张为无虚假运行数据的规划占位卡。
- [x] 明确通过 API 绑定和调用，现有 Runtime SDK 仅作参考且不导入、不打包、不部署、不调用。
- [x] 完成详细设计文档并通过完整性检查。
- [x] 记录关键 ADR、术语和本次设计报告并更新索引。
- [x] 补齐五大系统、14个组件的逐项总体验收和跨系统全链路验收目标。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 汇总需求、代码现状和基础设施验证 | 已完成 | 对照讨论、源码、Redis、PostgreSQL 和模型网关实测结论 |
| 2 | 选择并说明详细设计模板 | 已完成 | 采用 arc42 + C4 + Kubernetes KEP 的组合模板 |
| 3 | 编写总体设计和一期详细设计 | 已完成 | 设计覆盖14个组件总体验收及一期接口、数据、安全、测试、部署 |
| 4 | 建立术语表和关键架构 ADR | 已完成 | 术语无歧义，ADR 可追溯 |
| 5 | 更新项目与 records 索引并完成报告 | 已完成 | 索引可导航，报告记录验证结果 |

### 6. 当前进度

- 进行中：无，设计阶段已完成，等待评审 D1—D7。
- 已完成：关键需求澄清、现状代码审查、基础设施与模型网关可行性验证、模板调研、总体/一期详细设计、ADR、术语、报告和索引；已删除Memory Runtime Service层，并补齐14个组件的总体验收目标。
- 阻塞：无。仍未确定的实现选型会在设计中明确标记为“评审决策”，不会冒充已确认事实。

### 7. 验收记录

- [x] PDF 核心结构已读取
- [x] 菜单与测试台示意已确认
- [x] 产品用途、一期范围和数据隔离要求已确认
- [x] SDK/API 复用边界和组件/服务关系已确认
- [x] Control System Service、两个记忆Module/Interface和12张一期规划卡状态已确认
- [x] 五大系统、14个组件最终全部AVAILABLE的逐项验收标准已定义
- [x] 默认保存时间、敏感信息、管理员数据权限和 GenB 发放凭证已确认
- [x] 详细设计、ADR、术语和索引完成

测试结果：本阶段只做设计；已完成 Redis、PostgreSQL、Alaya Model Gateway 的前置可行性验证，详细证据和限制写入设计文档。

### 8. 风险和遗留问题

主要遗留风险：模型网关部分适配器依赖缺失且短期不会修复；当前PostgreSQL未提供pgvector；Redis本地配置不适合直接照搬生产；GenB现有后端细粒度权限尚未真正收敛；`control-system-service`的实现语言和仓库位置仍需评审确认；其他12个组件的实施顺序和责任团队尚待后续排期。

## 任务：将三项目 BAT 改为后台日志模式并创建桌面启停入口

### 1. 背景

现有 BAT 会为每个组件打开独立 CMD 窗口，影响桌面使用；隐藏运行后又需要可靠的停止方式，不能通过模糊进程名误杀其他项目。

### 2. 目标

GenB、GenC、GenO 全部后台启动，输出写入 D 盘日志；每个项目都有独立启动和停止入口，并在桌面建立六个快捷方式。

### 3. 范围

本次要做：后台启动、分组件日志、PID 状态文件、按进程树精准停止、三个停止 BAT、六个桌面快捷方式和真实启停验证。

本次不做：不恢复控制网页；不安装 Windows 服务；不部署服务器；不修改三个项目业务代码。

### 4. 完成标准

- [x] 启动项目时不弹出组件 CMD 窗口。
- [x] 每个组件的标准输出和错误写入 D 盘日志。
- [x] 停止脚本只结束对应启动记录中的进程树。
- [x] 桌面有 GenB、GenC、GenO 的启动和停止快捷方式。
- [x] 三个项目完成后台启停验证。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 实现公共后台进程控制脚本 | 已完成 | 语法、配置和 PID 记录通过 |
| 2 | 改造三个启动 BAT 并增加停止 BAT | 已完成 | 三项目配置自检通过 |
| 3 | 创建桌面快捷方式 | 已完成 | 六个 `.lnk` 目标正确 |
| 4 | 真实后台启停测试 | 已完成 | 三项目端口、日志、PID 和进程回收通过 |
| 5 | 更新说明和报告 | 已完成 | README、看板和报告完整 |

### 6. 当前进度

- 进行中：无。
- 已完成：后台启动、日志、PID 精准停止、六个桌面快捷方式、三项目真实验收；确认前端服务器 Nginx 主配置为 `/etc/nginx/conf.d/alaya-to.conf`。
- 阻塞：无。

### 7. 验收记录

- [x] 脚本语法
- [x] GenB 后台启停
- [x] GenC 后台启停
- [x] GenO 后台启停
- [x] 桌面快捷方式

测试结果：三个配置自检通过。GenB `8581/9000/9100`、GenC `5555/5174`、GenO `8000/5175/8081` 及任务队列均在隐藏进程中启动；9 个组件全部生成标准输出和错误日志；三个停止动作均删除 PID 状态文件并释放对应端口。桌面六个快捷方式已创建在 `D:\default\Desktop`。

### 8. 风险和遗留问题

后台启动没有可见控制台，故障需要查看日志；脚本会生成 PID 状态文件，并拒绝停止不属于本次启动记录的陌生进程。

## 任务：撤销本地控制网页并改用三个 BAT 启动脚本

### 1. 背景

本地控制网页持续重绘，用户决定不再保留网页和本地控制服务，只需要简单、直接的三个项目启动脚本。

### 2. 目标

完全关闭并删除控制网页，为 GenB、GenC、GenO 各提供一个双击启动的 BAT 文件。

### 3. 范围

本次删除控制网页、接口、配置、测试、日志、截图和对应报告；新增三个本地启动 BAT；不修改三个项目业务代码。

### 4. 完成标准

- [x] `17860` 控制端已停止，页面不能再访问。
- [x] 控制网页相关文件和生成物已删除。
- [x] GenB、GenC、GenO 各有一个 BAT 启动文件。
- [x] 三个 BAT 均通过依赖和路径自检；启动命令已复用此前真实启停通过的同一组命令。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 停止控制网页 | 已完成 | `17860` 不再监听 |
| 2 | 删除网页全部文件和生成物 | 已完成 | 文件清单无残留 |
| 3 | 新增三个 BAT | 已完成 | 脚本语法和路径检查 |
| 4 | 启动与依赖验证 | 已完成 | 三个 `--check` 全部通过；GenB 三个窗口实际拉起 |
| 5 | 更新说明和记录 | 已完成 | README、看板和报告一致 |

### 6. 当前进度

- 进行中：无。
- 已完成：停止控制端、删除网页方案及生成物、新增三个项目 BAT、依赖自检和说明文档。
- 阻塞：无。

### 7. 验收记录

- [x] 控制端停止
- [x] 网页文件删除
- [x] GenB BAT
- [x] GenC BAT
- [x] GenO BAT

测试结果：`17860` 已关闭；网页相关源文件、配置、测试、日志、截图和旧报告已删除；三个 BAT 的 `--check` 分别输出 `GENB_LOCAL_START_CHECK_OK`、`GENC_LOCAL_START_CHECK_OK`、`GENO_LOCAL_START_CHECK_OK`。GenB BAT 实际拉起了后端、管理端和门户进程，测试进程随后已全部关闭；GenC、GenO 使用的启动命令与撤销前已完成真实启停验证的命令一致。

### 8. 风险和遗留问题

BAT 会为每个组件打开独立命令窗口；关闭对应窗口即可停止，不再提供集中状态和停止按钮。

## 已撤销任务：开发 GenB、GenC、GenO 本地项目控制网页

### 1. 背景

三个项目由多个前后端进程组成，当前需要分别打开终端、记忆命令和端口，无法一眼判断项目是否已经运行，也容易停止错进程。

### 2. 目标

提供一个双击即可打开的本机网页，集中显示 GenB、GenC、GenO 的运行状态，并能安全启动、停止和打开各项目页面。

### 3. 范围

本次要做：增加仅监听 `127.0.0.1` 的临时本地控制入口；展示项目和组件状态；提供启动、停止、刷新、打开页面；记录工具启动的进程和日志；验证三项目状态识别及启停闭环。

本次不做：不部署到服务器；不修改三个项目业务代码；不安装常驻 Windows 服务；不停止无法确认属于对应项目的陌生进程；不把数据库密码、SSO secret 或私钥写入网页。

### 4. 完成标准

- [x] 双击启动入口后自动打开控制网页。
- [x] 页面清楚显示 GenB、GenC、GenO 是运行、部分运行、已停止还是异常。
- [x] 每个项目可以启动和停止，且页面状态会自动刷新。
- [x] 可以从页面打开三个项目的本地入口。
- [x] 停止操作只终止控制台启动并记录的进程，避免误杀其他程序。
- [x] 本地接口、前端交互和三组真实启停流程通过验证。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对现有部署中心、项目路径、端口和启动命令 | 已完成 | 三项目组件清单和入口明确 |
| 2 | 实现本机状态与进程控制接口 | 已完成 | 状态、启动、停止接口测试通过 |
| 3 | 实现项目控制网页 | 已完成 | 状态卡、按钮和错误提示可用 |
| 4 | 增加双击启动入口和日志 | 已完成 | 自动打开浏览器并产生分项目日志 |
| 5 | 执行真实启停与页面验收 | 已完成 | 三项目端口、健康接口、进程回收一致 |
| 6 | 更新说明和任务报告 | 已完成 | README、任务看板和报告完整 |

### 6. 当前进度

- 进行中：无。
- 已完成：该方案曾完成开发和测试，但已按用户要求于 2026-07-22 全部停止并删除，改用三个 BAT 启动脚本。
- 阻塞：无。

### 7. 验收记录

- [x] 本地控制接口
- [x] 项目状态识别
- [x] GenB 启停
- [x] GenC 启停
- [x] GenO 启停
- [x] 浏览器页面

测试结果：PowerShell、JavaScript 和 JSON 静态检查通过；本地接口自检输出 `ALL_PROJECT_CONTROL_CENTER_TESTS_PASSED`；GenB 3 个组件、GenC 2 个组件、GenO 4 个组件均完成真实启动和停止；后端及 GenO 推理服务健康接口通过；Chrome 页面显示 3 张项目卡、3 个启动按钮且控制台 0 错误。

### 8. 风险和遗留问题

GenO 完整运行依赖 PostgreSQL、Redis、Reasoning Service 等外部组件；页面会区分“核心页面可用”和“组件未全部运行”。已有但并非由本工具启动的进程只展示状态，不直接强制结束。

## 任务：补全 GenB 数据库并重构三项目交接文档

### 1. 背景

私密部署文档缺少 GenB 数据库连接；现有三份交接文档偏重当前修改，没有完整回答项目用途、项目间连接、历史改造、未完成事项、已知故障和新对话如何接手。

### 2. 目标

补全 GenB 数据库连接；使用统一的高质量交接模板重写 GenB、GenC、GenO 三份脱敏交接，让新对话无需重读整段历史聊天即可安全开始工作。

### 3. 范围

本次要做：更新私密部署文档；核对三个仓库、知识库、提交和历史记录；重写三份临时目录交接；验证敏感信息、路径和当前 Git 状态。

本次不做：不修改业务代码，不部署，不提交或推送，不在交接文档复制密码或私钥正文。

### 4. 完成标准

- [x] 私密部署文档包含经过用户确认的 GenB 数据库连接。
- [x] 三份交接均说明项目用途和系统关系。
- [x] 三份交接均包含已完成、未完成、历史故障和验证基线。
- [x] 三份交接均提供接手清单、禁止事项和建议技能。
- [x] 交接文件不包含秘密正文，引用路径有效。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 更新 GenB 数据库私密配置 | 已完成 | 字段存在且私密文件仍被排除 |
| 2 | 核对三项目当前事实 | 已完成 | Git、记录索引、计划和部署报告 |
| 3 | 确定统一交接模板 | 已完成 | 模板覆盖接手、运维和安全主题 |
| 4 | 重写三份交接文档 | 已完成 | 文件结构完整且内容各自定制 |
| 5 | 脱敏和引用验证 | 已完成 | 秘密扫描、路径检查、状态检查 |
| 6 | 更新报告和索引 | 已完成 | 任务报告可追溯 |

### 6. 当前进度

- 进行中：无。
- 已完成：GenB 数据库补全、三项目 Git/记录核对、统一模板、三份完整交接、官方最佳实践补充和全部验证。
- 阻塞：无。

### 7. 验收记录

- [x] GenB 数据库
- [x] GenB 交接
- [x] GenC 交接
- [x] GenO 交接
- [x] 脱敏检查
- [x] 引用路径检查

测试结果：三份交接必需章节无缺失；秘密扫描无命中；核心引用全部存在；三仓库 HEAD 与交接一致；私密部署文档继续被本地 Git 排除。

### 8. 风险和遗留问题

交接文档位于系统临时目录，适合马上启动新对话；长期事实必须引用项目知识库。秘密只保存在被本地 Git 排除的私密部署文档中。

## 任务：建立三项目私密部署架构与凭据文档

### 1. 背景

现有架构文档只简要列出 GenB 前后端服务器和路径，没有把 GenB、GenC、GenO 的部署关系、认证方式、服务器目录、启动脚本和必要凭据放在同一份可执行文档中。

### 2. 目标

建立一份本机私密部署架构文档，覆盖三个项目的完整部署拓扑和已授权记录的服务器凭据，并让 GenC、GenO 本地知识库可以直接定位该文档。

### 3. 范围

本次要做：记录前后端服务器、登录方式、密码/私钥、GenO 数据库、三个项目路径、启动脚本、访问地址、SSO 路由和验证入口；配置本地 Git 排除。

本次不做：不连接或修改服务器，不执行部署，不猜测当前没有可靠来源的 secret，不把私密文档加入 Git。

### 4. 完成标准

- [x] 私密文档覆盖 GenB、GenC、GenO。
- [x] 前端私钥和后端密码有明确可用记录。
- [x] 三项目的服务器位置、部署目录和启动方式完整。
- [x] 文档被根仓库本地 Git 排除。
- [x] GenC、GenO 本地索引能够直接找到该文档。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对现有架构、部署配置和凭据来源 | 已完成 | 文档、settings 和私钥文件 |
| 2 | 编写三项目私密部署拓扑 | 已完成 | 三项目表格和链路完整 |
| 3 | 配置本地 Git 排除 | 已完成 | `git check-ignore -v` |
| 4 | 接入 GenC、GenO 本地知识库 | 已完成 | 两个项目索引存在链接 |
| 5 | 验证并写报告 | 已完成 | 文件、排除和状态检查 |

### 6. 当前进度

- 进行中：无。
- 已完成：三项目私密部署拓扑、明文凭据、本地 Git 排除、GenC/GenO 知识库入口和验证报告。
- 阻塞：无。

### 7. 验收记录

- [x] 部署关系
- [x] 凭据记录
- [x] 三项目部署步骤
- [x] Git 本地排除
- [x] 知识库入口

测试结果：私钥正文与本机 `.pem` 完全一致；密码字段存在；私密文件被 `.git/info/exclude` 命中且不出现在 `git status`；GenC、GenO 索引仍为本地忽略文件。

### 8. 风险和遗留问题

该文档包含明文敏感信息，只允许保存在本机并由本地知识库引用；禁止提交、推送、发给同事或粘贴到普通报告。

## 任务：为 GenB、GenC、GenO 建立分对话交接与本地知识库

### 1. 背景

三个项目即将拆分到三个独立对话继续处理。GenB 已有较完整的 `records/`，GenC、GenO 缺少同等结构的本地知识库，容易让新对话重复调查或误用旧结论。

### 2. 目标

生成三份脱敏交接文档；为 GenC、GenO 建立可被新对话直接发现的本地知识库；确保新增知识库不会进入 Git 提交。

### 3. 范围

本次要做：核对三个仓库当前状态、生成交接文件、建立 GenC/GenO 本地 `records/` 和索引入口、配置本地 Git 排除、验证可读性和不提交状态。

本次不做：不修改业务代码，不提交或推送，不复制密码、私钥、数据库口令或 SSO secret。

### 4. 完成标准

- [x] GenB、GenC、GenO 各有一份独立交接文档。
- [x] GenC、GenO 各有本地知识库入口、索引和当前状态记录。
- [x] 新对话进入对应仓库后能从本地 `AGENTS.md` 找到知识库。
- [x] 所有新增本地知识库均被本地 Git 排除规则排除。
- [x] `git status` 不显示知识库文件，且没有改动业务代码。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对三仓库现状和已有文档 | 已完成 | 分支、状态、远端和目录清单 |
| 2 | 设计 GenC、GenO 本地知识库 | 已完成 | 入口和目录职责清晰 |
| 3 | 写三份脱敏交接文档 | 已完成 | 新对话所需信息完整 |
| 4 | 配置本地 Git 排除 | 已完成 | `git check-ignore` 命中 |
| 5 | 验证并写任务报告 | 已完成 | 文件可读、状态干净、报告入索引 |

### 6. 当前进度

- 进行中：无。
- 已完成：三份交接文档、GenC/GenO 本地知识库、Git 排除、可读性和敏感信息验证。
- 阻塞：无。

### 7. 验收记录

- [x] 三份交接文件
- [x] GenC 知识库
- [x] GenO 知识库
- [x] 本地 Git 排除
- [x] 敏感信息检查

测试结果：`git check-ignore` 全部命中；GenC 状态只保留既存 `.env` 暂存删除，GenO 状态为空；敏感信息扫描无命中；没有修改业务代码。

### 8. 风险和遗留问题

交接内容只能引用秘密所在的配置方式，不能写入秘密正文；仓库已有未提交修改属于现有工作，必须原样保留。

## 任务：建立 GenO 个人分支、修复本机环境、启动 GenC 权限开发并盘点 Codex 备份

### 1. 背景

GenB 和 GenO 有尚未进入可用远端分支的成果，GenC 权限配置尚未开发；服务器存在多批历史备份，需要先只读识别由 Codex 创建的备份。

### 2. 目标

只让 GenO 使用 `szharf-dev`；GenB 保持 `create-genB`、GenC 保持 `main`。安全推送当前成果，安装 D 盘 JDK 21、修复 WSL Bash，启动 GenC 权限开发，并生成不混入他人文件的 Codex 备份清单。

### 3. 范围

本次要做：只创建 GenO 个人分支、精准提交和推送、修复 JDK 21 与 WSL、实施 GenC 权限计划、只读核对和记录 Codex 备份。

本次不做：不强推正常分支，不提交生成物和秘密，不删除或移动任何备份。

### 4. 完成标准

- [x] GenO 使用并推送 `szharf-dev`，GenB/GenC 分支保持不变。
- [x] GenB 当前成果位于远端 `create-genB`，GenO 当前成果位于个人远端。
- [x] JDK 21、WSL `/bin/bash` 和 CDP Proxy 路径识别问题解决并验证。
- [ ] GenC 权限配置开始实施并逐步验证。
- [ ] Codex 备份清单与服务器文件对应，且没有处理他人文件。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对远端与工作区 | 已完成 | 三仓库状态和提交号 |
| 2 | 只创建 GenO 个人分支 | 已完成 | GenO 为 `szharf-dev`，另外两个不变 |
| 3 | 提交并推送 GenB、GenO | 已完成 | 远端提交核验 |
| 4 | 修复 JDK 21、WSL Bash 和 CDP 路径识别 | 已完成 | reasoning 构建、Bash/Node 版本和 wsPath 日志 |
| 5 | 启动 GenC 权限开发 | 未开始 | 按计划逐步测试 |
| 6 | 盘点 Codex 备份 | 未开始 | 记录位置、大小和用途 |
| 7 | 写报告 | 未开始 | 报告和索引完整 |

### 6. 当前进度

- 进行中：启动 GenC 权限开发，并整理已确认的 Codex 备份清单。
- 已完成：个人分支命名和任务计划；GenB `create-genB` 推送；GenO `szharf-dev` 创建并推送；D 盘 JDK 21、Ubuntu WSL、Bash、Node.js，以及 CDP Proxy 读取 Windows Chrome UUID 的兼容修复。
- 阻塞：CDP 最终连接等待用户在 Chrome 中完成一次“允许远程调试”安全确认；自动化不能代点浏览器安全权限。

### 7. 验收记录

- [x] GenB 推送
- [x] GenO 推送
- [ ] GenC 分支与权限测试
- [ ] 备份清单
- [ ] 敏感信息检查

测试结果：GenO reasoning 52 项 Maven 测试通过；WSL Bash 5.2.21、Node.js 22.23.1 可用；CDP Proxy 已发现 9222 端口及真实 UUID 路径，最终 `/targets` 等待 Chrome 用户授权。

### 8. 风险和遗留问题

备份盘点只读；任何清理动作必须单独确认。

## 任务：让 Genesis 统一门户保持简洁访问地址

### 1. 背景

Nginx 已能在 `/portal/login` 直接返回统一门户，但 Vue Router 启动时使用固定 `/genb-client/` 基路径，导致浏览器地址在页面加载后变成 `/genb-client/portal/login`。

### 2. 目标

访问、加载和登录过程中都保持 `http://16.162.33.130/portal/login`，同时兼容旧入口并保持静态资源、API 和其他客户端页面路径不变。

### 3. 范围

本次要做：动态选择 Vue Router 基路径；增加自动化测试；构建、部署 GenB 客户端并验证正式 URL。

本次不做：不修改后端、数据库、管理端、其他平台、根路径应用和现有 `/genb-client/` 资源/API 前缀。

### 4. 完成标准

- [x] 页面加载后 URL 仍为 `/portal/login`。
- [x] 正常登录后 URL 仍为 `/portal/login`。
- [x] 登录 API 继续使用 `/genb-client/api/`。
- [x] 旧统一门户入口和 Gen-B 业务入口不受影响。
- [x] 全部测试、构建、部署和正式验证通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 新增路由基路径纯函数和测试 | 已完成 | 短入口、旧入口、普通页面三组断言 |
| 2 | Vue Router 接入动态基路径 | 已完成 | 页面加载不改写短 URL |
| 3 | 运行客户端测试和构建 | 已完成 | 22 项 Vitest、vue-tsc、Vite 通过 |
| 4 | 备份并部署客户端 | 已完成 | 服务器备份和产物哈希 |
| 5 | 验证正式加载、登录及兼容入口 | 已完成 | 浏览器 URL、API 和兼容页面通过 |
| 6 | 写实施和部署记录 | 已完成 | 报告和部署记录已创建 |

### 6. 当前进度

- 进行中：无。
- 已完成：任务文档、失败测试、实现、全量测试、构建、部署和浏览器验收。
- 阻塞：无。

### 7. 验收记录

- [x] 路由基路径测试
- [x] 客户端全部测试
- [x] 客户端生产构建
- [x] 正式短 URL
- [x] 正式登录
- [x] 旧入口兼容

测试结果：22 项测试和生产构建通过；独立 Chromium 验证页面挂载及登录后 URL 均保持 `http://16.162.33.130/portal/login`，登录 API 继续使用 `/genb-client/api/`，旧入口和 Gen-B 业务页面返回 200。

### 8. 风险和遗留问题

只允许对 `/portal/login` 使用根路由基路径，不能把所有客户端路由迁到根路径，以免覆盖服务器现有系统。

## 任务：修正 GenB 品牌标题、统一门户入口和权限页按钮布局

### 1. 背景

正式环境浏览器页签仍显示“Gen-B 智能体平台”，统一门户地址带有 `/genb-client/` 项目前缀；管理端“统一门户权限”工具栏在当前宽度下把 Gen-O 按钮折到下一行，影响识别和操作。

### 2. 目标

浏览器页签统一显示 `Genesis Engine`；用户可使用 `http://16.162.33.130/portal/login` 访问统一门户并保留旧地址兼容；Gen-B 和 Gen-O 两个用户同步操作始终作为同一组显示在一行。

### 3. 范围

本次要做：修改客户端中英文页签标题和 HTML 默认标题；为正式 Nginx 增加精确的 `/portal/login` 内部入口；调整管理端现有工具栏按钮分组和样式；完成前端测试、构建及正式环境验证。

本次不做：不修改后端、数据库、同步接口语义和其他平台入口；不移除旧 `/genb-client/portal/login` 地址；不重构权限页面。

### 4. 完成标准

- [x] 中文和英文状态下浏览器页签均显示 `Genesis Engine`。
- [x] `/portal/login` 保持该地址并正常显示统一门户。
- [x] 旧 `/genb-client/portal/login` 仍可访问。
- [x] 两个平台用户操作按钮位于同一行，查询和刷新功能不变。
- [x] 客户端测试、管理端构建和客户端构建通过。
- [x] 正式页面、静态资源及登录接口验证通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对客户端路由和正式 Nginx location | 已完成 | 确认根路径属于其他系统，采用精确内部入口 |
| 2 | 修改品牌页签标题 | 已完成 | 单测验证两种语言的标题 |
| 3 | 调整权限页同步按钮分组 | 已完成 | 构建产物包含分组 DOM 和不换行 CSS |
| 4 | 增加正式门户短入口 | 已完成 | `nginx -t` 和 `/portal/login` HTTP 验证 |
| 5 | 运行前端测试与构建 | 已完成 | 19 项测试和两个生产构建通过 |
| 6 | 打包部署并验证 | 已完成 | 新旧入口、标题、按钮组资源均通过 |
| 7 | 写报告 | 已完成 | `records/reports/20260721-REPORT-genb-brand-portal-route-toolbar.md` |

### 6. 当前进度

- 进行中：无。
- 已完成：代码修改、测试、构建、正式部署和线上验证。
- 阻塞：无。浏览器 CDP 前置脚本因本机 WSL 缺少 `/bin/bash` 不可用，已用测试、构建产物和线上 HTTP 验证替代。

### 7. 验收记录

- [x] 客户端单元测试
- [x] 客户端生产构建
- [x] 管理端生产构建
- [x] 新旧统一门户入口
- [x] 线上标题
- [x] 线上按钮组资源
- [x] 登录接口

测试结果：客户端 19 项测试通过，客户端和管理端生产构建通过；新旧门户入口、客户端和管理端静态资源均返回 200；新入口不重定向且标题为 `Genesis Engine`；正常登录业务码 200 并返回 3 个平台详情。

### 8. 风险和遗留问题

服务器根 location 已由 `/ayala/dist` 中的其他系统使用，因此本次只为 `/portal/login` 增加精确入口，继续复用 `/genb-client/` 下的静态资源和 API。Gen-O 操作仍是实时刷新目录，没有改变为数据复制。

## 任务：部署 Genesis 统一登录门户性能优化

### 1. 背景

统一登录门户性能优化已在本地完成测试和生产构建，用户要求直接使用现成产物部署，不再重复构建。

### 2. 目标

将本次后端 JAR 和客户端 `dist` 安全部署到正式服务器，使线上登录直接返回平台列表并减少重复等待。

### 3. 范围

本次要做：核对现成产物；备份线上 JAR 和客户端目录；替换产物；使用现有脚本重启后端并重载 Nginx；验证健康检查、页面和真实登录链路。

本次不做：不重新执行 Maven、npm 测试或构建；不部署管理端；不修改数据库、Nginx 配置和 GenC 角色权限。

### 4. 完成标准

- [x] 本地产物晚于本次修改且 SHA-256 已记录。
- [x] 线上旧 JAR 和客户端目录均有可回滚备份。
- [x] 后端健康检查为 `UP`，新 JAR 哈希与本地一致。
- [x] 统一门户页面和静态资源正常返回。
- [x] 正常登录成功且响应包含平台详情；生产浏览器请求计数因本机自动化未结束未单独取证。
- [x] 部署记录包含验证结果和回滚位置。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对现成 JAR 和客户端 `dist` | 已完成 | 比较修改时间并计算 SHA-256 |
| 2 | 备份线上后端和客户端 | 已完成 | 服务器备份路径存在 |
| 3 | 上传并替换后端 JAR | 已完成 | 服务器 SHA-256 与本地一致 |
| 4 | 使用现有脚本重启后端 | 已完成 | 健康检查返回 `UP` |
| 5 | 上传并替换客户端 `dist` | 已完成 | 页面与主 JS 返回 200 |
| 6 | 验证统一门户真实登录 | 已完成 | 登录成功、平台详情存在、耗时有记录 |
| 7 | 写部署记录 | 已完成 | `records/deployments/20260721-DEPLOY-genesis-portal-login-performance.md` |

### 6. 当前进度

- 进行中：无。
- 已完成：现成产物部署、后端重启、Nginx 重载、线上页面和登录接口验收。
- 阻塞：无。

### 7. 验收记录

- [x] 产物完整性
- [x] 后端健康检查
- [x] 前端页面与静态资源
- [x] 正常登录
- [x] 登录响应包含 3 个平台详情

测试结果：后端 `UP`，服务器 JAR 哈希与本地一致；统一门户和主 JavaScript 返回 200；正常登录业务码 200 并返回 3 个平台详情，错误密码业务码 401。连续 3 次线上登录平均约 3.33 秒。生产浏览器自动化请求计数因本机进程未正常结束未单独取证，详情见部署记录。

### 8. 风险和遗留问题

本次按用户要求跳过重复构建，部署的是上一任务已通过全部测试的现成产物。相关源码已提交为 `7d3e9c9`，尚未推送远程；线上绝对耗时仍受网络和负载波动影响。

## 任务：优化 Genesis 统一登录门户登录速度

### 1. 背景

用户反馈统一登录门户登录速度慢。当前尚不能确认耗时发生在登录接口、远程数据库认证、登录后的平台权限查询，还是前端跳转和首屏请求；如果直接凭感觉修改，容易优化错位置。

### 2. 目标

建立可重复的登录计时基线，定位主要耗时并实施最小优化，使统一登录的关键链路明显缩短，同时不破坏密码校验、账号状态、平台权限和登录跳转。

### 3. 范围

本次要做：测量登录接口和登录后关键请求；定位数据库、代码或前端瓶颈；增加性能回归验证；实施精准优化；完成本地登录链路回归。

本次不做：暂不实施 GenC 角色权限可配置计划；不降低密码安全强度；不绕过账号状态和权限校验；不修改无关页面。

### 4. 完成标准

- [x] 有一条可重复运行、能捕获“登录慢”的计时命令或测试。
- [x] 优化前记录至少三次基线结果。
- [x] 找到主要耗时阶段并有数据证据。
- [x] 优化后同一基线明显改善且结果稳定。
- [x] 错误密码、禁用用户和正常登录行为没有改变。
- [x] 登录后平台列表和目标跳转正常。
- [x] 相关自动化测试及前后端构建通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 建立登录计时反馈循环 | 已完成 | 连续 5 次输出登录、平台列表和总耗时 |
| 2 | 重复测量并缩小复现范围 | 已完成 | 用户不存在约 0.2 秒、错误密码约 0.35 秒、正确登录原约 2.75 秒 |
| 3 | 列出并验证性能假设 | 已完成 | 定位逐平台授权/映射、多语言逐字段查询和前端重复请求 |
| 4 | 增加性能回归测试 | 已完成 | 测试强制批量读取授权、映射和平台翻译 |
| 5 | 实施最小优化 | 已完成 | 批量查询、稳定平台不重复写库、登录直接返回平台卡片 |
| 6 | 运行原始计时与功能回归 | 已完成 | 页面完整等待由约 5.73 秒降至约 1.94 秒；浏览器首卡约 2.45 秒 |
| 7 | 写报告 | 已完成 | `records/reports/20260721-REPORT-genesis-portal-login-performance.md` |

### 6. 当前进度

- 进行中：无。
- 已完成：统一门户登录性能优化、真实远程数据库计时、浏览器端到端验证、自动化测试和生产构建。
- 阻塞：无。GenC 角色权限可配置任务继续暂停，计划文档保留。

### 7. 验收记录

- [x] 登录接口计时
- [x] 登录后平台列表计时
- [x] 正确密码登录
- [x] 错误密码拒绝
- [x] 禁用用户拒绝
- [x] 登录跳转和首屏
- [x] 后端测试
- [x] 客户端测试与构建

测试结果：优化前 5 次平均为登录 2.75 秒、平台列表 2.98 秒，页面串行等待约 5.73 秒；优化后登录响应已包含平台卡片，5 次平均 1.94 秒，浏览器点击登录到首个平台卡片约 2.45 秒，且登录后平台列表重复请求为 0。后端 77 项测试、客户端 19 项测试、客户端生产构建均通过。

### 8. 风险和遗留问题

本次没有降低 BCrypt 强度或跳过任何权限校验。远程数据库单次网络往返仍影响绝对时间；如果未来平台或权限数量继续增加，应继续用批量查询回归测试约束，不能恢复逐平台查询。

## 任务：在 GenB 统一门户权限中配置 GenC 角色权限

### 1. 背景

GenC 已有 `ADMIN` 和 `USER` 两个角色，也已能根据权限编码控制菜单、路由和后端接口，但两个角色包含的权限由 GenB 后端初始化代码固定写入。统一门户权限页面目前只能给用户选择角色，只读显示最终权限，管理员不能调整角色本身的权限。

### 2. 目标

在 GenB 管理端“统一门户权限”页面集中配置 GenC 的 `ADMIN`、`USER` 角色权限。GenC 继续只负责执行权限，不增加独立权限管理入口。

### 3. 范围

本次要做：在统一门户权限页面增加角色权限配置；增加查询和原子替换角色权限的后端接口；修正初始化逻辑，避免重启补回已取消权限；验证 SSO 下发及 GenC 菜单、路由、接口执行。

本次不做：不创建第三种角色，不开放任意新权限编码，不在 GenC 增加管理页，不做已登录会话实时失效，不修改真实 `.env` 或服务器配置。

### 4. 完成标准

- [ ] 管理员可以在统一门户权限页面查看 `ADMIN`、`USER` 及其权限。
- [ ] 管理员可以勾选并保存每个角色的现有 GenC 权限。
- [ ] 保存后刷新页面仍显示数据库中的实际配置。
- [ ] 重启 GenB 后，被取消的权限不会被初始化程序补回。
- [ ] 用户重新从 Genesis 进入 GenC 后获得最新权限。
- [ ] GenC 菜单、直接 URL 和受保护接口都执行同一权限结果。
- [ ] 非管理员、跨平台权限、未知权限编码均被后端拒绝。
- [ ] GenB 和 GenC 相关自动化测试全部通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 固化当前角色权限基线 | 未开始 | 记录两个角色、四个权限及数据库关系数量 |
| 2 | 修正默认权限初始化策略 | 未开始 | 删除权限关系后重启，确认不会自动恢复 |
| 3 | 增加角色权限查询与保存接口 | 未开始 | 接口测试覆盖成功、越权和非法输入 |
| 4 | 在统一门户权限页增加“角色权限”区域 | 未开始 | 页面可加载、勾选、保存并刷新回显 |
| 5 | 验证统一权限解析与 SSO 下发 | 未开始 | ticket 验证结果包含保存后的权限集合 |
| 6 | 验证 GenC 执行效果 | 未开始 | 菜单、直接 URL、后端接口分别验证允许和拒绝 |
| 7 | 执行回归测试和构建 | 未开始 | GenB 后端、管理端及 GenC 权限测试通过 |
| 8 | 写报告并更新文档 | 未开始 | `records/reports/` 和索引有记录 |

### 6. 当前进度

- 进行中：详细设计和任务计划评审。
- 已完成：确认数据库模型已支持角色权限关系；确认当前缺少管理接口和可编辑页面；确认 GenC 已支持现有权限编码。
- 阻塞：无，等待用户确认计划后开始编码。

### 7. 验收记录

- [ ] 后端角色权限接口测试
- [ ] 初始化幂等与不回填测试
- [ ] 管理端交互测试
- [ ] GenB 后端构建
- [ ] GenB 管理端测试和构建
- [ ] GenC 菜单与路由权限测试
- [ ] SSO 完整链路测试

测试结果：尚未开始编码和测试。

### 8. 风险和遗留问题

权限变更第一阶段在用户重新从 Genesis 进入 GenC 后生效，已有 GenC Cookie 不实时刷新。角色只能组合 GenC 已登记的权限；新增页面或新接口仍需先在 GenC 代码中实现并登记稳定权限编码。

## 任务：提交并推送 GenB、GenC、GenO 到公司内部 Git 正常分支

### 1. 背景

三个项目的统一登录、统一权限及相关修复已经分别在本地完成，但部分提交仍未进入公司内部 Git 的正常使用分支，后续同事无法稳定拉取和部署。

### 2. 目标

把已经完成且验证通过的代码提交到三个项目既有正常分支：GenB `create-genB`、GenC `main`、GenO `dev`，并确认远端包含最终提交。

### 3. 范围

本次要做：同步远端、核对分支和提交差异、保护本地未提交文件、把已有工作合入指定分支、执行必要测试、推送并核验远端。

本次不做：不创建新分支，不提交构建缓存、`.env`、密码、私钥或无关文件，不强制推送，不绕过 protected branch 权限。

### 4. 完成标准

- [x] GenB 最终代码位于远端 `create-genB`。
- [x] GenC 最终代码位于远端 `main`。
- [ ] GenO 最终代码位于远端 `dev`。
- [x] 三个仓库没有新增临时分支。
- [x] 用户原有未提交文件得到保留。
- [x] 推送后已核对本地与远端提交号。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 拉取三个仓库远端引用 | 已完成 | 三个目标分支均已 `fetch` 并读取远端提交号 |
| 2 | 核对分支、提交和脏文件 | 已完成 | 已记录 ahead/behind，保留既存构建缓存和 `.env` 删除状态 |
| 3 | 整理 GenB 到 `create-genB` | 已完成 | `create-genB` 快进到 `08e2b5e`，没有新建分支 |
| 4 | 整理 GenC 到 `main` | 已完成 | 本地与远端均为 `e6c19b8`，既存 `.env` 删除状态未提交 |
| 5 | 整理 GenO 到 `dev` | 已完成 | 本地 `dev` 保留 3 个接入提交，敏感信息检查通过 |
| 6 | 测试并推送三个远端分支 | 阻塞 | GenB 已推送、GenC 已是最新；GenO 被 protected branch 权限拒绝 |
| 7 | 写任务报告 | 已完成 | `records/reports/20260721-REPORT-push-three-project-normal-branches.md` |

### 6. 当前进度

- 进行中：等待 GenO 项目 Maintainer 为当前账号开放 `dev` 推送权限，或由有权限的 Maintainer 推送本地 3 个提交。
- 已完成：GenB 已推送到 `create-genB`；GenC `main` 已是最新；三个项目均完成测试、敏感信息检查和远端提交号核验；没有新建分支。
- 阻塞：GenO `dev` 是 protected branch，服务器返回 `You are not allowed to push code to protected branches on this project`。

### 7. 验收记录

- [x] GenB 分支和远端核验
- [x] GenC 分支和远端核验
- [x] GenO 分支和远端核验
- [x] 敏感文件检查
- [x] 测试
- [ ] 推送（GenO 权限阻塞）

测试结果：GenB 后端 75 项、管理端 7 项通过；GenC 后端 31 项、前端 10 项通过；GenO 后端 4 项通过、前端构建成功。GenB 远端 `create-genB` 为 `08e2b5e`，GenC 远端 `main` 为 `e6c19b8`；GenO 本地 `dev` 为 `0c88f0e`、远端仍为 `e117d62`。

### 8. 风险和遗留问题

GenB 的构建缓存变动和 GenC 既存 `.env` 删除状态均已保留且没有提交。GenO 需要项目 Maintainer 修改 protected branch 权限或代为执行 `git push origin dev`；不得强制推送，也不创建替代分支。

## 任务：诊断 GenC 统一登录 callback 卡住

### 1. 背景

用户从 Genesis 统一门户进入 GenC 后，页面一直停留在 `/journey/sso/callback` 的“正在验证 Genesis 登录信息”状态。

### 2. 目标

复现线上问题并用页面请求、代理、后端端口和进程等待点的证据确定根因，不在未授权情况下修改或重启生产服务。

### 3. 范围

本次要做：检查浏览器请求、同域代理、后端健康接口、容器进程、网络连接和启动参数。

本次不做：不修改代码，不重启容器，不重新部署，不记录一次性 ticket 和服务器凭据。

### 4. 完成标准

- [x] 可以稳定复现 callback 卡住。
- [x] 找到具体 pending 请求。
- [x] 判断问题位于前端、Nginx、GenC 后端或 Genesis 后端中的哪一层。
- [x] 有进程级证据说明后端为什么不响应。
- [x] 给出立即恢复和永久修复方案。
- [x] 已重启 GenC 并完成真实统一登录回归测试。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 浏览器复现 | 已完成 | exchange 请求持续 pending |
| 2 | 最小 HTTP 对照 | 已完成 | 同域、直连、health 均稳定超时 |
| 3 | 检查容器和进程 | 已完成 | 容器存活、5555 监听、单 worker 不响应 |
| 4 | 检查 worker 等待点 | 已完成 | worker 阻塞在公网连接的 `recvfrom` |
| 5 | 输出处理方案 | 已完成 | 已区分立即恢复和永久修复 |
| 6 | 重启并回归测试 | 已完成 | health、exchange、真实门户登录和 GenC 业务接口通过 |

### 6. 当前进度

- 进行中：无，等待后续实施永久修复。
- 已完成：线上根因诊断、容器重启和完整 SSO 回归测试。
- 阻塞：无。

### 7. 验收记录

- [x] 浏览器 Network 检查
- [x] `/journey-api/health` 检查
- [x] 直连 `5555/health` 检查
- [x] GenB health 对照检查
- [x] Docker 进程、socket、syscall 检查
- [x] 容器重启与连续 health 检查
- [x] 无效 ticket 快速失败检查
- [x] Genesis 门户到 GenC 的真实登录链路

测试结果：故障时 GenC 所有请求稳定超时；唯一同步 Gunicorn worker 阻塞在来自公网地址的未完成连接。2026-07-21 12:19（Asia/Shanghai）重启 `journey_app` 后，本机、公网和同域 health 均恢复 200；无效 ticket 连续 3 次在 1 秒内返回 401；使用真实 Genesis 用户完成“门户登录 → 点击 GenC → ticket exchange 200 → GenC 首页 → 业务接口 200”。

### 8. 风险和遗留问题

本次重启已经恢复服务，但 5555 仍公开、worker 仍只有一个、超时仍为 1800 秒，问题可能复发。永久方案应限制来源地址、增加并发 worker、降低超时并配置容器自动重启。

## 任务：开发无服务版 Genesis 本地部署中心

### 1. 背景

GenB、GenC、GenO 当前分别依赖人工执行测试、构建、上传、备份、启动和验证，步骤分散且容易遗漏。用户希望在本机通过桌面页面完成部署，但不希望额外运行 Web 服务。

### 2. 目标

提供一个可直接启动的 Windows 桌面工具，让用户选择项目和组件后，一键执行测试、构建、部署和完整验证，并能查看实时进度、日志和历史记录。

### 3. 范围

本次要做：

- 开发 PowerShell 桌面界面；因当前 Windows 的 WPF 字体缓存异常，使用系统可用的 WinForms 实现。
- 开发 GenB、GenC、GenO 三个部署脚本和公共执行模块。
- 使用 Windows DPAPI 加密保存服务器凭据。
- 支持标准部署、快速部署、仅构建、仅验证和 Dry Run。
- 保存脱敏日志和部署历史，提供失败停止和人工回滚指引。

本次不做：

- 不启动本地 Web 服务，不开放端口。
- 不在代码、日志或命令行参数中明文保存密码、私钥和 SSO secret。
- 本轮不执行生产部署，不修改服务器和数据库。
- 不实现无人值守定时部署和数据库自动回滚。

### 4. 完成标准

- [x] 用户可以启动桌面界面并选择 GenB、GenC、GenO。
- [x] 用户可以配置组件、执行模式并看到逐步状态和实时日志。
- [x] 三个脚本均支持测试、构建、备份、替换、启动和验证流程。
- [x] 敏感配置经 DPAPI 加密，日志会脱敏。
- [x] Dry Run 不连接服务器、不修改项目和服务器。
- [x] PowerShell 语法检查、界面自检和三个项目 Dry Run 全部通过。
- [x] 已完成使用说明和任务报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 登记任务并检查本机环境 | 已完成 | PowerShell、WPF、DPAPI、SSH 命令可用 |
| 2 | 实现公共部署能力和加密配置 | 已完成 | DPAPI 加密往返与敏感值扫描通过 |
| 3 | 实现三个项目部署脚本 | 已完成 | 三个脚本 Dry Run 输出完整步骤并成功结束 |
| 4 | 实现桌面界面 | 已完成 | WinForms SelfTest 通过且窗口已启动并响应 |
| 5 | 执行完整本地验证 | 已完成 | 语法、静态检查、Dry Run 全通过 |
| 6 | 编写说明和报告 | 已完成 | README 和 `records/reports/` 已有记录 |

### 6. 当前进度

当前做到哪一步：

- 进行中：无，本地部署中心第一版已经完成。
- 已完成：公共模块、三个项目脚本、WinForms 桌面界面、DPAPI、日志历史、自检和文档。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] PowerShell 与 WPF 可用性
- [x] DPAPI 可用性
- [x] SSH、SCP、Tar、Git、Node 命令可用性
- [x] 脚本语法检查
- [x] 桌面界面自检
- [x] GenB Dry Run
- [x] GenC Dry Run
- [x] GenO Dry Run

测试结果：`Test-DeploymentCenter.ps1` 输出 `ALL_DEPLOYMENT_CENTER_TESTS_PASSED`；三个项目 Dry Run 均产生成功完成事件；敏感值扫描无命中；桌面窗口已实际启动并保持响应。未连接或修改生产服务器。

### 8. 风险和遗留问题

生产部署涉及远程文件替换，因此正式运行前仍需由用户确认项目、组件和提交号；服务器磁盘空间不足、工作区存在未提交修改、构建失败或健康检查失败时，工具会停止后续步骤。当前 Windows 的 WPF 字体缓存初始化异常，界面已改用系统可用的 WinForms；不影响功能和无服务架构。

## 任务：推送 GenO 统一登录代码并生成未提交交接文档

### 1. 背景

GenO 的 Genesis SSO、用户目录和前端 callback 已完成本地提交并部署上线，但 3 个提交仍只在本地 `dev`，尚未进入远端正常使用分支；同时需要一份不随代码提交、可直接发给同事的完整交接文档。

### 2. 目标

把已部署且验证通过的 GenO 代码推送到 `origin/dev`，并在项目仓库之外生成一份说明背景、目的、修改内容、作用、验证、部署和风险的交接文档。

### 3. 范围

本次要做：重新同步远端、确认可快进推送、推送现有 3 个提交、生成仓库外 Markdown 文档、确认文档未进入 Git。

本次不做：不新建分支，不修改或重新提交 GenO 代码，不把交接文档提交到 GenO，不记录密码、私钥和真实 SSO 密钥。

### 4. 完成标准

- [ ] `origin/dev` 包含 `18912f9`、`2c20b12`、`0c88f0e`（protected branch 权限阻塞）。
- [ ] GenO 本地 `dev` 与 `origin/dev` 一致。
- [x] 交接文档位于 `D:\default\Documents`，不在 GenO Git 工作区。
- [x] 文档覆盖背景、目的、范围、逐文件修改、接口、配置、验证、部署和风险。
- [x] 文档不包含任何真实凭据。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对本地提交和远端 | 已完成 | 本地领先 3、远端领先 0 |
| 2 | 推送正常分支 | 阻塞 | GitLab 拒绝向 protected `dev` 直接推送 |
| 3 | 生成仓库外交接文档 | 已完成 | 文件存在且章节完整 |
| 4 | 检查提交边界和敏感信息 | 已完成 | GenO 无新增改动，文档在仓库外且凭据扫描无命中 |
| 5 | 更新任务记录 | 已完成 | `records/reports/20260721-REPORT-geno-push-and-external-handoff.md` |

### 6. 当前进度

- 进行中：无。
- 已完成：确认提交关系、尝试推送、生成并检查仓库外交接文档。
- 阻塞：`dev` 是 protected branch，当前 SSH 用户无直接推送权限。

### 7. 验收记录

- [ ] 远端推送（protected branch 权限阻塞）
- [x] 远端提交核对
- [x] 文档完整性
- [x] 文档未提交
- [x] 敏感信息扫描

测试结果：远端同步后为本地领先 3、远端领先 0；推送被 GitLab pre-receive hook 拒绝，远端未改变。仓库外交接文档已生成且不包含真实凭据。

### 8. 风险和遗留问题

线上已经部署本地 3 个提交，但远端 `dev` 尚未包含；需要 Maintainer 放开权限或由用户允许使用团队 Merge Request 流程。交接文档已放在仓库外，不会随 GenO 提交。

## 任务：拉取并部署 GenC、GenO 最新代码

### 1. 背景

GenB 已部署 Genesis 统一登录和统一权限管理，但线上 GenC、GenO 后端仍是旧版本，SSO exchange 和 GenO 用户目录接口返回 404，导致统一门户无法完整免登录进入两个平台。

### 2. 目标

拉取 GenC、GenO 正常使用分支的最新代码，保留并确认我们已有的统一登录修改，按现有服务器规则完成可回滚部署，并验证页面、接口和 Genesis SSO 链路。

### 3. 范围

本次要做：拉取 GenC `main` 和 GenO `dev`、核对本地改动、构建测试、备份线上版本、部署两个项目的后端与前端、验证日志/接口/页面/SSO、编写部署记录。

本次不做：不新建分支，不提交或记录真实密码/私钥/SSO 密钥，不修改无关数据库数据，不覆盖无法确认归属的本地或线上文件。

### 4. 完成标准

- [x] 两个仓库已同步正常使用分支，且我们的修改仍在最终部署提交中。
- [x] GenC、GenO 后端测试和前端构建通过。
- [x] 线上原后端、JAR 和前端包按实际结构完成备份。
- [x] GenO 按 `/app/gen-o/start_build.sh` 启动，GenC 按 `/app/journey/start_rebuild.sh` 启动。
- [x] 两个平台页面、后端接口和关键日志正常。
- [x] Genesis 能读取 GenO 用户并签发/验证 GenC、GenO SSO ticket。
- [x] 已完成部署记录和任务报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对本地与服务器基线 | 已完成 | 已记录分支、提交、脏文件、线上目录/进程/配置名称 |
| 2 | 拉取正常使用分支 | 已完成 | GenC 与远端一致；GenO 远端无新提交且保留本地 3 个接入提交 |
| 3 | 构建与测试 | 已完成 | GenC 31+10、GenO 4 项测试及两个前端构建通过；未修改的 reasoning JAR 保留 |
| 4 | 部署 GenO | 已完成 | backend/frontend 已替换，JAR 已备份，`start_build.sh` 成功 |
| 5 | 部署 GenC | 已完成 | services/frontend 已替换，数据库已备份，`start_rebuild.sh` 成功 |
| 6 | 线上验收 | 已完成 | 进程、日志、页面、用户目录、两条 SSO 和防重放均通过 |
| 7 | 写记录 | 已完成 | `records/deployments/20260721-DEPLOY-genc-geno-unified-login.md` |

### 6. 当前进度

- 进行中：无，本次部署已经完成。
- 已完成：代码同步、测试构建、服务器备份、后端脚本启动、前端切换、GenC 同域 Cookie 修正和完整 SSO 验收。
- 阻塞：无。

### 7. 验收记录

- [x] GenC 后端测试/启动
- [x] GenC 前端构建/页面
- [x] GenO Python 后端测试/启动
- [x] GenO reasoning 启动（本轮无 Java 修改，保留原 JAR）
- [x] GenO 前端构建/页面
- [x] Genesis → GenC/GenO SSO

测试结果：GenC 后端 31/31、前端 10/10；GenO 后端 4/4；两个前端构建通过。线上 GenC/GenO SSO exchange、用户会话/profile、ticket 防重放、GenO 原登录、用户目录和页面资源全部通过。

### 8. 风险和遗留问题

GenC 工作区原有 `.env` 暂存删除已原样保留。GenO 3 个已部署的 Genesis 接入提交尚未推送 `origin/dev`，需尽快推送。后端服务器磁盘使用率 91%。本机 JDK 17 不满足 reasoning 的 release 21，但本轮没有 Java 改动，线上原 JAR 已备份并保持健康运行。

## 任务：部署并验证 GenB 前后端

### 1. 背景

GenB 已完成统一登录、权限管理和前端多语言等本地开发，需要把明确的版本部署到现有前后端服务器，并确认线上功能可用。

### 2. 目标

GenB 后端、业务客户端和管理端均完成可回滚部署；线上健康接口、登录、Genesis 门户、管理端及核心接口实际通过。

### 3. 范围

本次要做：核对正常协作分支与服务器现状、拉取最新代码、构建三部分、备份原版本、部署后端和两个前端、执行线上验收、写部署记录。

本次不做：不新建分支，不提交密钥，不修改 GenC/GenO 服务，不清理其他项目或服务器目录。

### 4. 完成标准

- [x] 明确本次部署的 Git 提交和配置来源。
- [x] 后端测试与构建通过。
- [x] 客户端、管理端构建通过。
- [x] 原后端 JAR、数据库 schema 和前端 dist 已备份，可回滚。
- [x] 后端服务健康且关键接口正常。
- [x] 线上登录、Genesis 门户、管理端路由及主要接口正常。
- [x] 已写部署记录和任务报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对分支、工作区和服务器 | 已完成 | 确认现网基线、目录、进程、Nginx 和健康状态 |
| 2 | 同步正常协作分支 | 已完成 | `create-genB=70931f6`；部署其连续后继 `08e2b5e` |
| 3 | 构建三部分 | 已完成 | 后端 75/75、客户端 19/19、两个前端构建通过 |
| 4 | 部署后端 | 已完成 | 新 JAR 哈希一致、PID `2042090`、健康 `UP`、无启动错误 |
| 5 | 部署两个前端 | 已完成 | Nginx 检查、SPA 路由、JS MIME 均通过 |
| 6 | 线上验收 | 已完成 | Genesis 登录、GenB token、profile、权限列表和正式 callback 配置通过 |
| 7 | 写记录 | 已完成 | `records/deployments/20260721-DEPLOY-genb-frontend-backend.md` |

### 6. 当前进度

- 进行中：无，本次 GenB 部署已完成。
- 已完成：服务器基线、干净构建、数据库/后端/前端备份、后端与两个前端切换、线上接口和静态资源验收。
- 阻塞：无。

### 7. 验收记录

- [x] 后端测试与构建
- [x] 客户端测试与构建
- [x] 管理端构建
- [x] 后端健康检查
- [x] Genesis 登录、GenB token 和 profile
- [x] 管理端路由、权限列表接口和静态资源

测试结果：后端 75/75、客户端 19/19；两个前端构建成功；线上后端 `UP`；Genesis 登录、GenB token exchange、profile 和 12 人权限列表均返回 200，列表耗时约 1.7 秒；前端路由与 JS 资源返回 200 且 MIME 正确。

### 8. 风险和遗留问题

GenB 已成功部署，但 GenC、GenO 生产后端尚未部署我们提交的 SSO 接口：两个 ticket exchange 探测均为 404，GenO 用户目录通过 GenB 调用时返回业务码 503。该问题不属于本次 GenB 部署范围，但会阻止 Genesis 到 GenC/GenO 的完整线上免登录链路。CDP 浏览器前置检查因本机 WSL 缺少 `/bin/bash` 未通过，本次页面验收采用构建、SPA 路由、静态资源、MIME 和真实 API 链路，未完成视觉截图验收。

## 任务：记录 GenC/GenO 正式地址并提交 GenO 全量代码修改说明

### 1. 背景

GenC、GenO 已明确正式访问地址；GenO 从公司仓库拉取后已经完成 Genesis SSO 和用户目录接入，需要把全部代码变化、用途和部署注意事项整理给同事，并提交到现有正常协作分支。

### 2. 目标

部署人员能使用正确的 GenC、GenO 地址；同事能通过一份文档看懂 GenO 改了哪里、为什么改、如何验证；GenO 代码和文档形成可追溯提交。

### 3. 范围

本次要做：记录正式访问地址和 SSO callback、核对 GenO 从 `origin/dev` 到当前的全部差异、编写代码交接文档、验证并提交 GenO。

本次不做：不记录密码或密钥，不描述数据库用户创建/映射等数据操作，不新建分支，不修改无关业务代码，不推送远程（除非用户另行要求）。

### 4. 完成标准

- [x] GenC 正式入口记录为 `http://16.162.33.130/journey/`。
- [x] GenO 正式入口记录为 `http://16.162.33.130/geno`。
- [x] 部署时需要替换的两个 SSO callback 已写清。
- [x] GenO 文档覆盖从 `origin/dev` 到当前的全部代码修改及作用。
- [x] 文档不包含数据库数据操作、密码或密钥。
- [x] GenO 测试通过，提交范围准确且位于现有 `dev` 分支。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 记录正式入口与部署 callback | 已完成 | 四个正式 URL 均返回 HTTP 200 |
| 2 | 核对 GenO 全部差异 | 已完成 | 已比较 `origin/dev..HEAD` 并同步远程 41 个提交 |
| 3 | 编写同事交接文档 | 已完成 | 已逐文件说明 17 个功能修改文件及作用 |
| 4 | 执行测试并提交 | 已完成 | 后端 4/4、前端构建通过；提交 `0c88f0e` |
| 5 | 写任务报告 | 已完成 | `records/reports/20260720-REPORT-genc-geno-production-urls-and-geno-handoff.md` |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：正式地址及 callback 记录、公网只读核验、远程 `dev` 同步、GenO 全量修改交接文档、测试和本地提交。
- 阻塞：无。

### 7. 验收记录

- [x] 正式地址核对
- [x] GenO 后端测试
- [x] GenO 前端构建
- [x] Git 提交检查

测试结果：GenC、GenO 的入口及 callback 均返回 HTTP 200；GenO 后端相关测试 4/4 通过；前端 `npm run build` 成功。存在项目原有 Pydantic 命名警告和 bundle 体积警告，不影响本次通过结论。

### 8. 风险和遗留问题

正式访问入口与 SSO callback 不是同一个 URL；部署时必须保留各项目实际 callback 路由，且服务端密钥只能通过运行环境配置。GenO 当前 `dev` 比 `origin/dev` 领先 3 个本地提交，尚未推送，等待用户明确要求。

## 任务：新增 shizhenhua、sunny 管理员并提交 GenC 权限列表优化

### 1. 背景

需要继续新增两名统一门户管理员，并把已经完成验收的 GenC 权限列表性能优化连同同事 AI 可读的修改文档提交到当前代码分支。

### 2. 目标

`shizhenhua`、`sunny` 能以同名初始密码登录 Genesis 和 GenO，均为管理员且完成 GenO 映射；性能优化代码、测试和交接文档形成一个干净提交。

### 3. 范围

本次要做：创建/同步两名用户、设置管理员、建立 GenO 映射、登录验收、复核 GenC 权限结果、编写同事 AI 交接文档、精确提交相关文件。

本次不做：不提交 `node_modules` 或构建缓存，不推送远程，不修改无关代码，不在文档记录密码或数据库凭据。

### 4. 完成标准

- [x] 两名用户在 Genesis、GenO 中均为管理员并可登录。
- [x] 两名用户的 Genesis → GenO 映射已解锁。
- [x] GenC 权限列表优化的测试和真实接口继续通过。
- [x] 修改文档可供同事 AI 直接读取。
- [x] Git 提交只包含本次相关代码、测试和文档。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对两名 GenO 用户和统一门户现状 | 已完成 | GenO 已存在、Genesis 原不存在 |
| 2 | 创建、同步并映射用户 | 已完成 | 两端真实登录和映射接口通过 |
| 3 | 复核 GenC 优化 | 已完成 | 75 项测试；12 人接口平均 1,167ms |
| 4 | 编写同事 AI 修改文档 | 已完成 | 文档含原因、文件、验证和注意事项 |
| 5 | 精确提交并推送 | 已完成 | GenB `08e2b5e` 已推送原功能分支；GenC `e6c19b8` 已快进推送至 `origin/main` |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：两名管理员创建、同步、GenO 映射、真实登录；75 项测试、12 人接口计时、交接文档、精确 Git 提交及远程推送；GenC 已进入同事正常使用的 `main`。
- 阻塞：无。

### 7. 验收记录

- [x] Genesis 登录
- [x] GenO 登录
- [x] GenO 映射
- [x] 后端完整测试
- [x] Git 提交检查

### 8. 风险和遗留问题

用户名同名初始密码安全性较弱，只按用户已经明确的规则设置；正式使用后应修改。数据库变更不会进入 Git，交接文档必须明确这部分需要在其他环境单独执行。

补充分支约定：自 2026-07-20 起，用户未明确指定时，直接使用各仓库现有正常协作分支，不再自行新建临时分支。

## 任务：诊断 Genesis 用户权限列表接口 15 秒延迟

### 1. 背景

管理员把用户映射为 GenC 管理员后，请求 `access-users?keyword=` 约需 15 秒，已经影响权限管理页面使用。

### 2. 目标

稳定复现并定位耗时来源，给出可验证的修复结论；未验证前不把任务标记为完成。

### 3. 范围

本次要做：测量空关键字与单用户查询、核对数据库查询和外部调用次数、定位根因、形成回归验证。

本次不做：不修改无关页面，不变更用户权限数据，不推送代码。

### 4. 完成标准

- [x] 有一条可以稳定捕获慢接口的自动化命令。
- [x] 明确 15 秒分别耗在哪些调用。
- [x] 空关键字接口恢复到可接受时间且结果不变。
- [x] 相关测试通过并写报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 建立接口计时反馈环 | 已完成 | 连续请求稳定复现约 15 秒并按阈值判定红/绿 |
| 2 | 缩小慢调用范围 | 已完成 | 已对比 0 人、1 人、10 人和 GenO 目录 |
| 3 | 验证候选根因 | 已完成 | 日志采样确认 10 人产生约 162 条 Hibernate SQL |
| 4 | 修复与回归 | 已完成 | 原始脚本由 15,039ms 降至 1,139ms，权限数据一致 |
| 5 | 写诊断记录 | 已完成 | `records/bugs/20260720-BUG-genesis-access-users-n-plus-one-latency.md` |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：稳定复现、N+1 根因确认、批量查询优化、查询数回归测试、75 项完整测试、最新 JAR 重启和真实远程数据库验收。
- 阻塞：无。

### 7. 验收记录

- [x] 空关键字接口计时
- [x] 单用户接口计时
- [x] 数据库/外部服务调用定位
- [x] 修复后回归

### 8. 风险和遗留问题

接口当前返回全部用户，数据规模继续增长后仍建议增加服务端分页；本次已消除随“用户数 × 平台数”增长的 N+1 查询。

## 任务：创建统一门户与 GenO 管理员用户并核清 GenC 历史会话归属

### 1. 背景

需要把陈涛、陈佳春、王蕴杰、李伟东、方肖恩、周旻意、段怡帆、李华慧统一建立为中文姓名全拼账号，并确保这些账号在 GenO 中存在且具备管理员权限；同时需要说明 GenC 历史会话如何与登录用户关联。

### 2. 目标

八名用户可通过统一门户使用管理员身份，并与 GenO 用户目录保持一致；给出开发和非开发人员都能理解的 GenC 历史会话归属说明。

### 3. 范围

本次要做：核对 Genesis 与 GenO 用户、创建缺失账号、修正明显拼音错误、验证管理员角色、检查 GenC 会话归属代码和数据结构、写报告。

本次不做：不推送代码，不部署服务器应用，不公开或提交初始密码，不合并同名人员之外的账号。

### 4. 完成标准

- [ ] 八名用户在统一门户中存在，用户名为姓名全拼。
- [ ] 八名用户在 GenO 中存在且均为管理员。
- [ ] 不因拼音错误为同一人产生重复账号。
- [ ] 已通过真实接口或数据库复核结果。
- [ ] 已写清 GenC 历史会话与用户的关联方式及现有限制。
- [ ] 已完成任务报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对用户创建入口与现有账号 | 已完成 | 已输出八人差异清单 |
| 2 | 创建或修正统一门户用户 | 已完成 | 管理接口返回八个全拼账号 |
| 3 | 创建或修正 GenO 用户 | 已完成 | GenO 返回八个管理员账号；`dunyifan` 与 `duanyifan` 独立存在 |
| 4 | 核查 GenC 历史会话归属 | 已完成 | 代码、表字段与请求链条相互印证 |
| 5 | 完成真实验证 | 已完成 | 八人分别登录 Genesis、GenO 成功；原 `dunyifan` 登录成功 |
| 6 | 写报告 | 已完成 | `records/reports/20260720-REPORT-unified-admin-users-and-genc-session-ownership.md` |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：八名统一门户管理员创建与同步、GenO 管理员核对和新增、平台映射、真实登录验证、GenC 会话归属核查。按用户确认，`dunyifan` 与 `duanyifan` 是两个独立账号；前者保留原 UUID，后者使用新 UUID。
- 阻塞：暂时没有。

### 7. 验收记录

- [x] Genesis 用户核对
- [x] GenO 用户核对
- [x] 管理员角色核对
- [x] GenC 会话归属代码核对

测试结果：八个名单账号均以姓名全拼密码成功登录 Genesis 和 GenO；原 `dunyifan` 也成功登录 GenO；GenC 用户隔离测试 8/8 通过。

### 8. 风险和遗留问题

当前按用户明确要求使用姓名全拼作为初始密码，安全性较弱，正式使用前建议由每位用户自行修改。GenC 服务端会话和业务数据按用户隔离，但首页会话索引仍主要保存在当前浏览器的 `localStorage`；换浏览器或清空缓存后，服务端消息仍在，却缺少完整的跨设备会话发现入口。

## 任务：修复 test_user 的 GenC 普通用户映射并切换最新本地运行态

### 1. 背景

`test_user` 在统一权限管理中配置为 GenC 普通用户时报错；8581 仍运行审查修复前的旧 JAR；同时已获得 GenO 远程 `ontoprompt` 数据库连接信息。

### 2. 目标

定位并修复映射错误，让最新 GenB 后端在本地运行，并确认 GenO 远程数据库中的用户数据结构。

### 3. 范围

本次要做：复现映射错误、修复并测试、停止旧 8581、启动最新 JAR、只读核查 GenO 远程数据库、记录结果。

本次不做：不推送代码，不部署服务器应用，不修改 GenO 远程数据库。

### 4. 完成标准

- [x] `test_user` 可以保存为 GenC `USER`。
- [x] 保存后平台角色和权限返回正确。
- [x] 最新 GenB JAR 在 8581 运行。
- [x] GenO 远程数据库完成只读结构和用户数据核查。
- [x] 已完成测试并写报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 复现并读取服务端错误 | 已完成 | 日志确认 `UnexpectedRollbackException` |
| 2 | 修复映射逻辑 | 已完成 | RED 后 GREEN；事务测试和表单测试通过 |
| 3 | 构建并重启 8581 | 已完成 | 最新 JAR、远程 GenB 数据库、健康接口 200 |
| 4 | 验证 test_user 映射 | 已完成 | 保存 200，USER、2 权限、入口解锁 |
| 5 | 只读核查 GenO 远程数据库 | 已完成 | PostgreSQL 只读事务确认 17 个用户；8000 已切换远程库 |
| 6 | 写报告 | 已完成 | `records/reports/20260720-REPORT-test-user-genc-mapping-and-geno-remote-database.md` |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：映射修复、74 项后端测试、7 项表单测试、管理端构建、最新 JAR 重启、远程 GenB/GenO 运行态切换和真实接口验证。
- 阻塞：无。

### 7. 验收记录

- [x] 映射接口
- [x] GenB 后端测试
- [x] 8581 健康检查
- [x] GenO 数据库只读查询

### 8. 风险和遗留问题

GenB 和 GenO 是两套不同数据库：8581 连接远程 GenB，8000 连接远程 `ontoprompt`。当前启动参数只存在于进程环境，机器重启后需要使用安全的本地启动脚本或环境管理方式恢复，不能把密码提交到 Git。

更新时间：2026-07-15

本文件用于记录当前已经确定要做的任务、执行状态、验证结果和下一步。每次开发前必须先更新本文件；每完成一步必须勾选；任务结束后必须写报告到 `records/reports/`。

## 使用规则

1. 任务开始前：
   - 明确任务目标。
   - 写清成功标准。
   - 拆成可验证步骤。
   - 标记当前步骤为 `进行中`。

2. 执行过程中：
   - 每完成一步就把状态改为 `已完成`。
   - 遇到阻塞写明原因和需要的输入。
   - 不把未验证内容标记为完成。

3. 任务结束后：
   - 写验证结果。
   - 写剩余风险。
   - 写下一步。
   - 生成报告到 `records/reports/`。

## 状态说明

| 状态 | 含义 |
|---|---|
| 未开始 | 已确认要做，但还没动手。 |
| 进行中 | 当前正在做。 |
| 已完成 | 已实现并验证。 |
| 阻塞 | 无法继续，需要用户输入或外部条件。 |
| 延后 | 当前不做，后续再排。 |

## 任务：定位真实 GenO 数据源并接通用户同步（未完成）

### 1. 背景

本地 GenO 只有 admin，需要确认当前远程 PostgreSQL 是否存在 GenO 对应数据库、用户表，以及 Genesis 映射相关表。

### 2. 目标

定位同事实际使用的 GenO 数据源，确认新增用户，并让 Gen-B 管理端同步列表能够读取该用户。

### 3. 范围

本次要做：

- 使用现有服务端连接配置进行只读连接。
- 检查数据库、schema、表及用户相关记录数。
- 检查 Genesis 映射和授权表。
- 获取并核查同事实际使用的 GenO 后端或数据库。
- 验证新增用户能够出现在 Gen-B 管理端同步列表。

本次不做：

- 不创建、修改或删除任何数据库对象和数据。
- 不输出数据库密码。

### 4. 完成标准

- [x] 成功连接或明确连接被拒原因。
- [x] 列出当前可见数据库和相关 schema。
- [x] 明确是否存在 GenO 用户库/表。
- [x] 明确 Genesis 映射表和记录情况。
- [ ] 获得同事实际 GenO 后端或数据库地址。
- [ ] 在真实 GenO 数据源中确认新增用户。
- [ ] Gen-B 管理端同步列表显示新增用户。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 读取并脱敏解析现有连接配置 | 已完成 | 未输出密码 |
| 2 | 测试 SSL/非 SSL 只读连接 | 已完成 | 通过 SSH 隧道只读连接成功 |
| 3 | 查询数据库、schema 和表 | 已完成 | 检查 3 个数据库和全部业务表 |
| 4 | 查询用户与映射记录数量 | 已完成 | 用户、映射、授权数量已核对 |
| 5 | 写核查报告 | 已完成 | `records/reports/` 已记录 |
| 6 | 获取同事实际 GenO 数据源 | 阻塞 | 需要后端地址或数据库连接信息 |
| 7 | 连接真实 GenO 并确认新增用户 | 未开始 | 用户目录或只读数据库查询 |
| 8 | 接通并验证 Gen-B 同步 | 未开始 | 管理端出现新增用户 |

### 6. 当前进度

- 进行中：无，任务尚未完成。
- 已完成：通过服务器 SSH 隧道只读检查 `alaya_to`、`genb`、`postgres`；确认这些库中没有 GenO 对应数据库和 38 表结构。
- 阻塞：缺少同事实际使用的 GenO 后端地址或数据库连接信息，无法确认新增用户并接通同步。

### 7. 验收记录

- [x] 远程连接
- [x] 数据库列表
- [x] 表结构
- [x] 用户记录
- [x] Genesis 映射记录
- [ ] 同事真实 GenO 用户目录
- [ ] 新增用户同步验证

测试结果：当前已知远程 PostgreSQL使用 `transaction_read_only=on` 完成核查且未写数据；其中没有 GenO 数据库，Gen-B 中只有 admin 的 GEN_O 映射。最终同步目标未完成。

### 8. 风险和遗留问题

当前任务保持“未完成/阻塞”。解阻条件：同事提供实际 GenO 后端 URL 及匹配的服务端集成密钥，或提供实际 GenO 数据库地址和只读账号。获得后还需确认新增用户并完成管理端同步验收。

---

## 任务：启动三套本地项目并核查 GenO 用户同步数据

### 1. 背景

需要同时运行 Gen-B、GenC、GenO 前后端；管理端同步 GenO 用户后仍只有 admin 可映射，与同事新增用户的预期不一致。

### 2. 目标

确保三套项目本地可访问，并查明同步接口实际读取哪个 GenO 数据库及其中用户数量。

### 3. 范围

本次要做：

- 检查并启动三套项目前后端。
- 复现 GenO 用户目录返回数量。
- 核对 GenO 数据源和本地用户表。
- 给出是否为最新数据及处理方案。

本次不做：

- 未确认前不覆盖或复制同事数据库。
- 不修改用户数据。

### 4. 完成标准

- [x] 三套项目前后端均可访问。
- [x] 明确同步请求连接地址和数据库。
- [x] 明确当前用户数量与用户名。
- [x] 明确同事新增用户未出现的原因。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 检查全部端口和健康接口 | 已完成 | 7 个端口和 6 个 HTTP 地址正常 |
| 2 | 补启缺失服务 | 已完成 | 三套项目前后端已启动 |
| 3 | 调用 GenO 用户目录接口 | 已完成 | 直接和 Gen-B 转发都返回 1 人 |
| 4 | 检查 GenO 数据源与用户表 | 已完成 | SQLite 用户表只有 admin |
| 5 | 记录结论 | 已完成 | `records/reports/` 已记录 |

### 6. 当前进度

- 进行中：无，启动和诊断已完成。
- 已完成：三套项目前后端启动；确认同步读取本地 GenO SQLite，用户目录只有 admin。
- 阻塞：无。

### 7. 验收记录

- [x] Gen-B：客户端、管理端、后端正常
- [x] GenC：前后端正常
- [x] GenO：前后端正常
- [x] GenO 用户目录：直接与转发均返回 1 人
- [x] 数据库用户表：只有 admin

测试结果：所有页面和健康接口返回 200；GenO 用户目录链路正常，但本地数据不是同事新增用户所在的数据源。

### 8. 风险和遗留问题

要读取同事新增用户，需要获得同事 GenO 后端地址和配套服务端密钥，或获得其数据库副本。推荐直接调用同事 GenO 后端用户目录，避免复制数据库形成两份数据。

---

## 任务：将国际化集成结果合入公司 create-genB

### 1. 背景

集成分支已经上传公司 Git，用户确认不再只保留审阅分支，需要让同事直接从 `create-genB` 拉取。

### 2. 目标

把已验证的 `70931f6` 安全合入公司远端 `create-genB`。

### 3. 范围

本次要做：

- 重新获取远端 `create-genB` 最新提交。
- 确认能否快进，或先合并新增提交。
- 非强制推送并核对远端哈希。

本次不做：

- 不使用强制推送。
- 不部署服务器。

### 4. 完成标准

- [x] 没有覆盖同事远端新提交。
- [x] 远端 `create-genB` 包含 `70931f6`。
- [x] 推送后远端哈希核对通过。
- [x] 已形成合入记录。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 检查本地工作区和集成提交 | 已完成 | 工作区干净、HEAD 为 `70931f6` |
| 2 | 获取远端最新 `create-genB` | 已完成 | 远端为 `ed438de`，是集成提交祖先 |
| 3 | 合入并推送 | 已完成 | 快进到 `70931f6` |
| 4 | 核对远端结果 | 已完成 | 远端完整哈希与本地一致 |
| 5 | 写合入记录 | 已完成 | `records/reports/` 已记录 |

### 6. 当前进度

- 进行中：无，合入已完成。
- 已完成：公司远端 `create-genB` 已从 `ed438de` 快进到 `70931f6`，完整哈希核对一致。
- 阻塞：无。

### 7. 验收记录

- [x] 远端更新检查
- [x] 非强制推送
- [x] 远端哈希核对

测试结果：普通快进推送成功；`70931f6` 是远端 `create-genB` 当前提交。

### 8. 风险和遗留问题

同事拉取前若本地有未提交修改，应先保存；本次远端历史没有重写，正常 `git pull` 即可。

---

## 任务：发布客户端国际化集成分支到公司 Git

### 1. 背景

本地国际化与统一登录合并已经完成并验证，需要把结果交给同事继续查看和联调。

### 2. 目标

将本地集成结果安全推送到公司 Git 的 `client-i18n-merge-20260715` 分支。

### 3. 范围

本次要做：

- 检查本地工作区、提交和远端分支状态。
- 不使用强制推送地发布目标分支。
- 推送后核对远端提交。

本次不做：

- 不合入同事的 `create-genB` 主开发分支。
- 不部署服务器。

### 4. 完成标准

- [x] 工作区干净且测试提交为 `70931f6`。
- [x] 远端目标分支没有被覆盖的新提交。
- [x] 公司 Git 的目标分支指向 `70931f6`。
- [x] 已形成发布记录。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 检查本地分支和工作区 | 已完成 | Git 状态干净、HEAD 正确 |
| 2 | 获取远端最新状态 | 已完成 | 远端目标分支原本不存在 |
| 3 | 推送目标分支 | 已完成 | 非强制 push 成功 |
| 4 | 核对远端提交 | 已完成 | `ls-remote` 返回 `70931f6` |
| 5 | 写发布记录 | 已完成 | `records/reports/` 已记录 |

### 6. 当前进度

- 进行中：无，发布已完成。
- 已完成：公司 Git 已创建 `client-i18n-merge-20260715`，本地与远端均为 `70931f6`，本地分支已跟踪远端。
- 阻塞：无。

### 7. 验收记录

- [x] 远端读取
- [x] 分支推送
- [x] 提交核对

测试结果：非强制推送成功；远端完整哈希与本地一致。

### 8. 风险和遗留问题

本次只发布独立集成分支，尚未创建 Merge Request，也没有合入 `create-genB`。后续由同事审阅后决定是否合并主开发分支。

---

## 任务：修复 Genesis 登录返回 500

### 1. 背景

本地 Genesis 登录在账号校验成功后返回 `Request failed with status code 500`，导致统一门户无法登录。

### 2. 目标

恢复 Genesis 登录，并确认登录后的用户和平台接口正常。

### 3. 范围

本次要做：

- 捕获 Genesis 后端异常。
- 验证源码与运行字节码是否一致。
- 全量重编译并重启本地后端。
- 真实调用登录和授权接口回归。

本次不做：

- 不修改业务代码。
- 不提交或部署服务器。

### 4. 完成标准

- [x] Genesis 登录返回成功。
- [x] 新 token 可以获取当前用户。
- [x] 三个平台列表可以返回。
- [x] 后端不再出现同类 `NoSuchMethodError`。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 找到 500 的服务端堆栈 | 已完成 | 日志定位到 `NoSuchMethodError` |
| 2 | 建立稳定复现 | 已完成 | `javap` 证明运行类缺少源码已有方法 |
| 3 | 全量清理和构建 | 已完成 | `mvn clean package`、19 项测试通过 |
| 4 | 重启 Genesis 与 GenC SSO | 已完成 | 8581、5555 正常监听 |
| 5 | 回归真实登录链路 | 已完成 | login、me、platforms 均返回 200 |
| 6 | 写故障报告 | 已完成 | `records/reports/` 已记录 |

### 6. 当前进度

- 进行中：无，问题已修复。
- 已完成：清理旧字节码、生成独立运行 JAR、重启服务和真实登录回归。
- 阻塞：无。

### 7. 验收记录

- [x] 后端 19 项测试通过。
- [x] Genesis 登录返回 200。
- [x] 当前用户接口返回 200。
- [x] 平台列表返回 200，共 3 项。
- [x] 新日志无 `NoSuchMethodError`。

测试结果：全部通过。

### 8. 风险和遗留问题

项目仓库历史上跟踪过部分 `target/classes`，直接使用增量 `mvn spring-boot:run` 可能再次混入旧字节码。本地合并或切换分支后必须先执行 `mvn clean`。

---

## 任务：启动本地 GenC 与 GenO 联调环境

### 1. 背景

Gen-B 与 Genesis 已在本地运行，但 GenC、GenO 尚未启动，无法继续验证三个系统的本地入口和统一登录。

### 2. 目标

让 GenC 和 GenO 的本地页面、后端及现有必要服务可以访问，并与 Genesis 本地回调地址保持一致。

### 3. 范围

本次要做：

- 启动 GenC 前后端。
- 启动 GenO 前后端和可用的后台服务。
- 避开两个前端默认端口冲突。
- 检查页面、健康接口和启动日志。

本次不做：

- 不修改或提交同事代码。
- 不部署服务器。
- 不安装缺失运行时，若存在依赖缺口先明确报告。

### 4. 完成标准

- [x] GenC 页面与后端可以访问。
- [x] GenO 页面与后端可以访问。
- [x] Genesis、GenC、GenO 本地端口不冲突。
- [x] 已检查健康接口与启动日志。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 确认启动命令、环境和端口 | 已完成 | README、配置和端口检查 |
| 2 | 启动 GenC | 已完成 | 页面和健康接口返回 200 |
| 3 | 启动 GenO | 已完成 | 页面、API、Celery 正常 |
| 4 | 检查 Genesis 联调地址 | 已完成 | 本地回调使用 5174/5175 |
| 5 | 写启动记录 | 已完成 | `records/reports/` 已记录 |

### 6. 当前进度

- 进行中：无，主体服务启动任务已完成。
- 已完成：GenC `5174/5555`、GenO `5175/8000`、GenO Celery 和 Genesis `8581` 均正常；Redis 认证已通过进程环境接入。
- 阻塞：GenO Java 推理服务要求 Java 21+，当前本机 Java 为 17，推理功能暂不可用。

### 7. 验收记录

- [x] GenC 页面：`http://127.0.0.1:5174/journey/` 返回 200
- [x] GenC 健康接口：`http://127.0.0.1:5555/health` 返回 200
- [x] GenO 页面：`http://127.0.0.1:5175/` 返回 200
- [x] GenO API：健康接口和 API 文档返回 200
- [x] Genesis 门户：`http://127.0.0.1:9100/portal/login` 返回 200

测试结果：主体页面和后端全部通过；GenO Celery 日志显示 `ready`。GenO Java 推理服务未启动。

### 8. 风险和遗留问题

GenO 的 Java 推理服务暂不能用 Java 17 启动；若主体页面需要执行推理功能，再单独安装到 D 盘并记录。

---

## 任务：合并同事前端国际化与本地完整语言链路

### 1. 背景

同事在公司 `create-genB` 分支完成了客户端和 Genesis 固定页面中英文，本地则完成了后端动态翻译、`X-Locale`、语言刷新以及 Gen-C/Gen-O SSO。两边从同一提交分叉，并重叠修改 30 个文件，直接覆盖任一版本都会丢失功能。

### 2. 目标

形成一套可以本地运行和测试的合并版本：页面展示采用同事成果，接口、动态数据和统一登录采用本地已验证逻辑，并给同事一份清楚说明修改原因和维护边界的文档。

### 3. 范围

本次要做：

- 在独立集成分支合并 `company/create-genB` 最新代码。
- 解决客户端、Genesis 门户和管理端语言文件冲突。
- 保留 Gen-B、Gen-C、Gen-O 统一登录和动态英文链路。
- 统一成一套前端语言入口，删除重复实现。
- 执行后端、客户端、管理端和真实浏览器回归。
- 编写面向同事的合并说明文档。

本次不做：

- 不推送公司 Git，不部署服务器。
- 不覆盖用户、授权或智能体中文原始数据。
- 不修改 Gen-C、Gen-O 仓库代码。

### 4. 完成标准

- [x] 同事最新 4 个提交已进入集成分支。
- [x] 页面保持同事的展示和固定文案效果。
- [x] 客户端与 Genesis 请求继续发送 `X-Locale`。
- [x] 动态智能体和平台字段继续使用 `display*`。
- [x] Gen-C、Gen-O Ticket 和 Gen-B Token Exchange 没有回退。
- [x] 两套语言目录已统一，不存在混用。
- [x] 后端、两个前端构建、自动化测试和浏览器联调通过。
- [x] 已形成可交给同事阅读的合并说明。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 保存当前工作区并创建集成分支 | 已完成 | stash、分支和状态检查 |
| 2 | 合并同事最新分支 | 已完成 | Git 历史包含 `ed438de` |
| 3 | 恢复本地改动并解决冲突 | 已完成 | diff 和语言模块引用检查 |
| 4 | 回归统一登录与动态英文 | 已完成 | 接口测试及真实浏览器测试 |
| 5 | 执行完整构建和测试 | 已完成 | Maven、客户端、管理端全部通过 |
| 6 | 编写同事说明文档 | 已完成 | 文档包含保留项、原因和验证 |
| 7 | 本地提交合并结果 | 已完成 | `70931f6`，未推送 |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：已合入同事最新 `ed438de`，解决 28 个恢复冲突；统一 `src/i18n`；保留 `X-Locale`、`display*`、Gen-C/Gen-O Ticket 和 Gen-B Token Exchange；完成测试、构建、浏览器验收、同事文档和本地提交 `70931f6`。
- 阻塞：无。

### 7. 验收记录

- [x] Git 合并历史
- [x] 后端测试
- [x] 客户端测试与构建
- [x] 管理端构建
- [x] Genesis 登录页面
- [x] Gen-B/Gen-C/Gen-O 入口与 SSO 自动化测试
- [x] 中英文动态数据逻辑

测试结果：后端 19 项、客户端 19 项全部通过；客户端和管理端生产构建通过；真实浏览器验证登录页语言切换、标题同步、Genesis 门户及三平台卡片通过。真实账号跨系统落地留待联调环境验收。

### 8. 风险和遗留问题

本次未推送和部署。真实账号点击 Gen-C、Gen-O 并进入下游系统尚未在本地执行；当前由后端 SSO 自动化测试覆盖，联调环境仍需补做三平台落地验收。

---

## 任务：清理客户端英文接口全部中文残留

### 1. 背景

英文模式下，固定按钮和部分分类已经是英文，但客户端目录接口的多个智能体名称、描述和其他展示字段仍显示中文。用户提供的跨境金融智能体只是示例，实际需要审计整个接口返回。英文页面因此中英混杂，不能视为完成。

### 2. 目标

让客户端目录接口的全部智能体在英文请求时，名称、描述、分类、业务属性、状态和运行状态等展示字段不再残留中文，同时保持中文请求和记录数量不变。

### 3. 范围

本次要做：

- 建立可重复的全量接口检查，准确识别每个展示字段的中文残留和记录丢失。
- 核对全部智能体 ID、英文源字段和翻译表。
- 补齐初始化脚本与当前联调数据库中的缺失英文数据。
- 重新验证英文接口、中文接口和真实页面。

本次不做：

- 不修改 Git 分支，不提交、不推送。
- 不用前端硬编码覆盖数据库动态内容。

### 4. 完成标准

- [x] 英文接口返回的智能体数量与中文接口一致。
- [x] 全部智能体的英文展示字段不含中文残留。
- [x] 用户示例和原有英文智能体都仍存在。
- [x] 中文接口仍返回对应中文内容。
- [x] 初始化脚本和当前联调数据库保持一致。
- [x] 后端测试、客户端测试和真实页面验证通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 建立缺陷复现检查 | 已完成 | 英文接口全量检测记录数、字段和中文字符 |
| 2 | 核对翻译数据和代码链路 | 已完成 | 对照 agentId、字段和翻译表 |
| 3 | 补齐缺失英文翻译 | 已完成 | 更新初始化脚本和联调数据库 |
| 4 | 回归接口与页面 | 已完成 | 中英文 API、浏览器和自动化测试 |
| 5 | 更新报告 | 已完成 | 八段式报告记录根因和验证 |

### 6. 当前进度

- 进行中：无，本地修复和验证已完成。
- 已完成：全量 80 条接口审计；补齐 70 个旅程智能体与 3 个系统智能体翻译、17 类分类词典；更新联调数据库；接口、页面和测试回归。
- 阻塞：无。

### 7. 验收记录

- [x] 英文接口
- [x] 中文接口
- [x] 后端测试
- [x] 客户端测试
- [x] 真实页面

测试结果：修复前 80 条目录存在 209 处英文展示字段中文残留；修复后英文和中文目录均为 80 条，英文目录和“我的智能体”展示字段中文残留为 0。后端 19 项测试、客户端 19 项测试和客户端构建通过；真实英文市场 70 张卡片及分类标题无中文残留，控制台 0 错误。

### 8. 风险和遗留问题

当前后端连接服务器 PostgreSQL，本次只向 `i18n_texts` 更新或插入 146 条 `AGENT/en-US` 记录，没有修改智能体原始中文、用户或授权。原始字段仍保留中文，英文页面必须使用 `display*` 字段。新环境需要按数据库发布流程执行 `i18n_texts_init.sql`。

---

## 任务：接入 Gen-B 客户端与 Genesis 门户中英文切换

### 1. 背景

管理端已经有中英文按钮，Gen-B 后端核心接口也能根据 `X-Locale` 返回英文；但业务客户端没有语言状态、没有切换按钮，也没有向后端发送语言请求头。Genesis 门户复用业务客户端工程，因此同样只能显示中文。

### 2. 目标

在业务客户端和 Genesis 门户中使用同一套语言状态。用户切换语言后，固定页面文案、后端动态内容请求和刷新后的语言选择保持一致。

### 3. 范围

本次要做：

- 为业务客户端接入 Vue i18n 和中英文词典。
- 增加可复用语言切换组件。
- 在客户端主导航和 Genesis 门户显示语言按钮。
- 为客户端与 Genesis 请求统一增加 `X-Locale`。
- 将客户端和 Genesis 门户的核心固定文案改为语言 key。
- 验证默认中文、切换英文、刷新保持和后端语言请求头。

本次不做：

- 不重写管理端已有语言功能。
- 不翻译申请理由、审核意见等用户输入原文。
- 不修改 Gen-C、Gen-O 的页面语言。
- 不提交、推送或部署，除非用户后续明确要求。

### 4. 完成标准

- [x] 客户端主导航可以切换简体中文和 English。
- [x] Genesis 门户可以切换简体中文和 English。
- [x] 两个入口共享并持久化同一个语言选择。
- [x] 客户端和 Genesis API 请求携带正确的 `X-Locale`。
- [x] 英文模式优先展示后端英文/本地化字段。
- [x] 默认中文和现有登录、门户跳转功能没有损坏。
- [x] 客户端单元测试和生产构建通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对管理端、客户端、Genesis 当前语言能力 | 已完成 | 管理端已有；客户端和门户均未接入 |
| 2 | 增加共享语言状态、词典和切换组件 | 已完成 | 语言可切换并写入 localStorage |
| 3 | 接入客户端主导航和 Genesis 门户 | 已完成 | 两个入口都显示同一语言 |
| 4 | 接入 API 请求头和后端展示字段 | 已完成 | 请求含 `X-Locale`，英文数据可显示 |
| 5 | 转换核心页面固定文案 | 已完成 | 英文模式不残留核心固定中文 |
| 6 | 执行测试和构建 | 已完成 | `npm run test:run`、`npm run build` |
| 7 | 更新文档和任务报告 | 已完成 | `records/reports/` 有八段式记录 |
| 8 | 使用真实后端完成本地联调 | 已完成 | 8581、9000、9100 运行，真实数据中英文切换通过 |
| 9 | 合并同事客户端与 Genesis 实现 | 延后 | 公司 Git 恢复后拉取并解决冲突 |

### 6. 当前进度

- 进行中：无，本地实现和验收已完成。
- 已完成：客户端与 Genesis 共用语言状态、按钮、核心文案、请求语言头和动态展示字段；客户端 19 项测试、后端 18 项测试、两个前端构建和真实数据库浏览器联调通过；本地 8581、9000、9100 正在运行。
- 阻塞：无。

### 7. 验收记录

- [x] 默认中文
- [x] 切换英文
- [x] 刷新保持语言
- [x] 客户端接口语言请求头
- [x] Genesis 接口语言请求头
- [x] 客户端单元测试
- [x] 客户端生产构建

测试结果：客户端 `npm run test:run` 共 7 个测试文件、19 项测试全部通过；后端 `mvn clean test` 共 18 项测试通过；客户端和管理端生产构建通过。真实浏览器连接当前 PostgreSQL 后端，验证了 Genesis 登录、客户端登录、英文动态智能体名称、切回中文、跨入口共享和刷新保持；客户端与 Genesis 请求都捕获到 `zh-CN` 和 `en-US`，浏览器控制台 0 错误。

### 8. 风险和遗留问题

用户输入和数据库缺失英文的数据仍按设计回退原文。管理端继续使用自己的语言存储，本次只让业务客户端与 Genesis 门户共享。同事也已实现一版客户端与 Genesis 中英文功能，但公司 Git 当前不可用；本地先完成开发，等服务器恢复后必须先拉取同事版本、逐文件解决冲突，不能直接覆盖。本地后端按现有配置连接服务器 PostgreSQL，`ddl-auto=update`。

---

## 任务：编写 Genesis 统一登录全链路说明

### 1. 背景

Genesis、Gen-B、Gen-C、Gen-O 已形成三种不同的登录接入方式，但现有信息分散在代码、专项接入文档和历史报告中。开发人员能查到接口，非开发人员却不容易理解为什么三个系统的处理方式不同。

### 2. 目标

形成一份开发和非开发人员都能读懂的独立文档，说明各系统改了什么、用户怎样获得访问权、点击平台后发生什么，以及登录凭证为什么不能直接共用。

### 3. 范围

本次要做：

- 说明 Gen-O 已完成的修改。
- 说明 Gen-C 本地待提交的修改。
- 用流程图、表格和分步骤说明 Gen-B、Gen-C、Gen-O 的完整登录链路。
- 标明关键接口、配置、数据关系和代码入口。
- 更新项目文档索引。

本次不做：

- 不修改统一登录业务代码。
- 不提交、推送或部署代码。
- 不改变现有平台权限和用户数据。

### 4. 完成标准

- [x] 非开发人员可以理解统一登录的总体过程。
- [x] 开发人员可以找到各平台关键接口、配置和代码入口。
- [x] 文档明确区分授权、账号映射、ticket 和目标系统登录态。
- [x] 文档明确说明三套平台接入方式的差异。
- [x] 文档已加入项目索引。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对 Gen-O、Gen-C 和 Genesis 当前代码 | 已完成 | Git 状态、提交和关键接口已核对 |
| 2 | 编写统一登录说明文档 | 已完成 | 16 个章节、流程图、表格和检查清单完整 |
| 3 | 更新文档索引 | 已完成 | `docs/INDEX.md`、`PROJECT_INDEX.md` 有入口 |
| 4 | 写任务报告 | 已完成 | `records/reports/20260715-REPORT-genesis-unified-login-chain-document.md` |

### 6. 当前进度

- 进行中：无，本任务已完成。
- 已完成：Gen-O 两个相关提交、Gen-C 本地改动、Genesis 三条跳转链路核对；说明文档、链接检查、索引和报告。
- 阻塞：无。

### 7. 验收记录

- [x] 文档结构检查
- [x] 三平台流程对照检查
- [x] 接口和代码路径检查
- [x] 项目索引检查

测试结果：文档共 462 行、45 个标题，16 个本地代码链接全部存在；三平台流程、关键接口和配置名称已与当前代码核对。

### 8. 风险和遗留问题

本文必须明确区分“已经提交的 Gen-O 修改”和“尚未提交的 Gen-C 本地修改”，避免读者误认为所有代码都已上线。

---

## 任务：让用户从 Genesis 免登录进入 Gen-C

### 1. 背景

Genesis 已经支持统一登录、平台授权和一次性登录凭证，Gen-O 也已完成本地接入。Gen-C 最新代码已经获取并在本地运行，但当前没有登录系统，所有用户都被当成 `superuser`，数据只按前端传来的会话编号区分。

如果直接把 Genesis 门户链接指向 Gen-C，虽然页面能打开，但 Gen-C 无法确认当前是谁，也无法阻止用户查看或修改其他人的画布、聊天和私有知识库。

### 2. 目标

让获得 Gen-C 访问权的用户从 Genesis 点击 Gen-C 后直接进入，不需要再次登录，并确保每个用户只能访问自己的数据。

用普通话描述，不写技术细节。

### 3. 范围

本次要做：

- Genesis 为 Gen-C 发放短时、一次性登录凭证。
- Gen-C 服务端验证凭证并建立自己的登录状态。
- Gen-C 记录当前登录用户，替换写死的 `superuser`。
- 画布、聊天、会话和私有知识库按用户隔离。
- Gen-C 前端增加统一登录回调和未登录处理。
- Genesis 门户点击 Gen-C 时走统一登录流程。
- Genesis 管理端继续控制用户是否可以访问 Gen-C。
- 为新增或修改的关键代码写详细注释，说明“为什么增加”和安全边界。
- 补充自动化测试、浏览器联调、配置示例和任务报告。

本次不做：

- 不做“同步 Gen-C 用户”按钮，因为 Gen-C 当前没有独立用户目录可同步。
- 不给 Gen-C 增加账号密码注册和登录页。
- 不删除或改坏 Gen-O、Gen-B 已有统一登录流程。
- 不实现跨平台统一退出。
- 不提交真实共享密钥、服务器地址或数据库密码。
- 未经再次确认不推送远端、不部署服务器。

### 4. 完成标准

满足下面这些条件，才算完成：

- [x] `admin` 获得 Gen-C 权限后，可以从 Genesis 免登录进入 Gen-C。
- [x] 没有 Gen-C 权限的用户不能获得登录凭证。
- [x] 登录凭证过期后不能使用，使用一次后不能再次使用。
- [x] Gen-C 只接受服务端验证成功的 Genesis 身份。
- [x] 未登录直接访问受保护页面时不能读取业务数据。
- [x] 用户只能读取和修改自己的画布、聊天、会话和私有知识库。
- [x] Gen-B、Gen-O 原有登录和门户跳转没有坏。
- [x] 后端测试、前端构建、接口测试和浏览器端到端测试全部通过。
- [x] 新增配置只有示例值，真实密钥没有进入 Git。
- [x] 关键代码注释写清为什么增加，不只描述代码表面行为。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 确认方案、影响范围和数据迁移方式 | 已完成 | 用户确认开始；历史数据归 admin；首次 SSO 自动建最小用户 |
| 2 | 为现有安全问题补失败测试 | 已完成 | 7 条认证、越权和历史迁移测试按纵向切片先失败后通过 |
| 3 | 扩展 Genesis 的 Gen-C 登录凭证能力 | 已完成 | 独立 client 配置、自动映射和 Gen-C ticket 测试通过 |
| 4 | 增加 Gen-C 服务端登录状态 | 已完成 | ticket exchange、HttpOnly Cookie 和 `/api/auth/me` 测试通过 |
| 5 | 改造 Gen-C 用户数据隔离 | 已完成 | 画布、聊天、知识库、槽位和历史数据归属测试通过 |
| 6 | 增加 Gen-C 前端回调和登录检查 | 已完成 | callback 成功进入首页，刷新仍保持登录 |
| 7 | 接通 Genesis 门户 Gen-C 跳转 | 已完成 | 点击 Gen-C 申请凭证并跳到正确地址 |
| 8 | 完整回归和安全检查 | 已完成 | 测试、构建、格式检查和浏览器联调通过 |
| 9 | 提交代码 | 未开始 | 用户确认后分别提交 Gen-B、Gen-C 本地代码 |
| 10 | 写报告 | 已完成 | `records/reports/20260714-REPORT-genesis-genc-sso-implementation.md` |

### 6. 当前进度

当前做到哪一步：

- 进行中：无，本地实现和验收已完成，等待用户确认是否提交。
- 已完成：任务方案和最新分支确认；Genesis `GEN_C` ticket 与自动映射；Gen-C 最小用户、HttpOnly Cookie；画布、聊天、私有知识库和槽位按用户隔离；旧数据仅归 `admin`；7 条 Gen-C 后端测试、三个前端构建、Genesis 到 Gen-C 浏览器端到端联调通过。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] Genesis 后端测试
- [x] Gen-C 后端认证和数据隔离测试
- [x] Gen-B 客户端构建
- [x] Gen-C 前端构建
- [x] Genesis 登录并进入 Gen-C
- [x] 无权限用户拒绝
- [x] 登录凭证过期和重复使用拒绝
- [x] 两个用户的数据隔离
- [x] Gen-B、Gen-O 回归

测试结果：

Genesis 后端完整测试通过；Gen-B 客户端、管理端和 Gen-C 前端生产构建通过；Gen-C 7 条认证、未登录拒绝、跨用户隔离和历史数据归属测试通过。从本地 Genesis 门户点击 Gen-C 后进入 `http://127.0.0.1:5174/journey/`，刷新后仍保持登录。

### 8. 风险和遗留问题

- Gen-C 已按 Genesis 稳定用户 ID 在首次 SSO 时建立最小本地用户；当前不提供独立账号密码登录和用户同步按钮。
- 旧 `superuser` 数据只由 Genesis `admin` 认领，普通用户从空数据开始。
- Gen-C 根目录 `.env` 已停止 Git 跟踪并保留在本地；如果历史文件曾包含真实凭据，仍建议轮换。
- Gen-C 全量 `vue-tsc --noEmit` 存在接入前已有的类型错误，本次只确认生产构建和新增链路通过。
- 正式部署仍需配置 callback URL、独立共享密钥、HTTPS Cookie、CORS 和 Nginx；本次未部署。

详细方案：`records/plans/20260714-PLAN-genesis-genc-sso.md`。

---

## 任务：获取 Gen-C 代码并完成本地启动验证

### 1. 背景

Gen-C 代码目前位于远程私有 GitLab，本地工作区还没有该项目。要进一步设计和实施统一登录，必须先取得完整代码并确认项目能在本地正常启动。

如果不先完成本地运行，后续接入方案只能依赖网页浏览，无法验证依赖、配置、接口和页面行为。

### 2. 目标

把 Gen-C 最新代码放到 D 盘，在不影响现有 Gen-B、Gen-O 服务的前提下启动前后端，并确认主要页面和健康接口可以本地访问。

### 3. 范围

本次要做：

- 克隆 Gen-C 最新代码到 `D:\code\opencode\genb\gen-c`。
- 检查分支、配置、依赖和启动方式。
- 所有新增依赖安装在 D 盘并记录。
- 启动后端和前端，验证健康接口及主要页面。
- 记录现有代码中影响统一登录接入的实际问题。

本次不做：

- 不修改 Gen-C 统一登录代码。
- 不提交或推送 Gen-C 代码。
- 不部署服务器。
- 不修改 Gen-B、Gen-O 现有运行配置。

### 4. 完成标准

满足下面这些条件，才算完成：

- [x] Gen-C 代码已完整克隆到 D 盘。
- [x] 已确认当前分支和远程最新状态。
- [x] 后端可以在本地启动并访问健康接口。
- [x] 前端可以在本地启动并打开主要页面。
- [x] 原有 Gen-B、Gen-O 本地服务没有被占用或破坏。
- [x] 所有安装下载已写入安装下载记录。
- [x] 已形成实际代码验证后的接入结论。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 更新任务看板并确认目标目录 | 已完成 | 目标目录不存在，任务范围已记录 |
| 2 | 克隆最新代码 | 已完成 | 现有 SSH 密钥验证成功，`main` 已克隆到 D 盘 |
| 3 | 检查配置与依赖 | 已完成 | 后端使用 SQLite 和 5555；前端改用命令行端口 5174，不修改代码 |
| 4 | 安装后端和前端依赖 | 已完成 | D 盘依赖安装完成，`pip check` 与前端构建通过，记录已补充 |
| 5 | 启动后端 | 已完成 | 5555 正常监听，健康、Provider 和画布读取接口均返回 200 |
| 6 | 启动前端 | 已完成 | 5174 正常监听，首页和编辑器真实浏览器验收通过 |
| 7 | 回归现有本地服务 | 已完成 | 5173、8000、8581、9000、9100 均保持监听 |
| 8 | 写报告 | 已完成 | `records/reports/20260714-REPORT-genc-local-startup.md` 已创建 |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：代码下载、密钥定位记录、配置检查、D 盘依赖安装、构建、前后端启动、接口验证、真实浏览器页面验证、原服务回归和报告。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] Git 分支与远程状态
- [x] 后端依赖与健康接口
- [x] 前端构建与开发服务器
- [x] 主要页面
- [x] 原有本地服务端口

测试结果：

全部通过。`main` 与 `origin/main` 一致；`pip check` 和 `npm run build` 通过；`/health`、`/api/llm/providers`、`/api/canvas` 返回 200；首页与编辑器均完整渲染，浏览器控制台和页面运行错误为空；原有 5173、8000、8581、9000、9100 端口仍正常监听。

### 8. 风险和遗留问题

仓库已提交 `.env`，包含外部服务配置项，应在后续提交前改为示例文件并轮换可能暴露的凭据。`requirements.txt` 遗漏了运行时依赖 `requests`，本地已临时安装但未修改同事代码。项目没有登录校验，后端直接信任请求传入的 `session_id`，数据库中的 `user_id` 又默认写成 `superuser`；接入 Genesis 前必须增加服务端身份校验和按 Genesis 用户隔离数据，不能只在前端拼接用户参数。

---

## 任务：让 Genesis 实时选择 Gen-O 用户并自动关联同名账号

### 1. 背景

当前 Genesis 权限页面需要管理员手工填写 Gen-O 用户 ID 和用户名，既难理解，也容易填错。Genesis 还不知道 Gen-O 现有用户，无法在用户第一次进入 Gen-O 时自动建立账号对应关系。

如果不处理，管理员需要在两个系统之间来回复制信息，错误映射还可能导致用户无法进入 Gen-O。

### 2. 目标

管理员可以在 Genesis 权限页面直接刷新并选择 Gen-O 用户；当尚未关联的用户第一次进入 Gen-O 时，如果两个系统只有一个同名账号，系统自动建立关联。

同步账号关联与授予访问权限保持分离，系统不会因为找到同名用户就自动授权。

### 3. 范围

本次要做：

- Gen-O 提供受服务端密钥保护的用户目录接口。
- Genesis 后端实时读取 Gen-O 用户目录。
- 管理页面增加“刷新 Gen-O 用户”并使用下拉选择账号。
- 第一次进入 Gen-O 时，对唯一同名账号自动建立关联。
- 增加后端、前端测试并完成本地联调。

本次不做：

- 不增加每天定时同步任务。
- 不把 Gen-O 用户复制到 Genesis 数据库。
- 不自动创建 Gen-O 用户。
- 不自动授予或撤销平台访问权限。
- 不部署服务器。

### 4. 完成标准

满足下面这些条件，才算完成：

- [x] 管理员可以实时刷新 Gen-O 用户列表。
- [x] 管理员可以从下拉列表选择 Gen-O 用户，不需要手填 UUID。
- [x] 唯一同名账号可以在第一次进入 Gen-O 时自动关联。
- [x] 未授权用户不会因为自动关联而获得访问权限。
- [x] Gen-O 用户接口不能被浏览器或无密钥请求直接读取。
- [x] 原有 Gen-B 同步、权限管理和 Gen-O SSO 没有坏。
- [x] 已完成后端测试、前端构建和浏览器联调。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 理解现有代码和文档 | 已完成 | 已确认 SSO、账号映射、权限页面和 Gen-O 用户表影响范围 |
| 2 | 补充任务测试并实现 Gen-O 用户目录接口 | 已完成 | 无凭据请求被拒绝，正确密钥返回最小用户列表 |
| 3 | 实现 Genesis 实时查询和首次自动关联 | 已完成 | 服务测试覆盖唯一匹配、无匹配和人工停用场景 |
| 4 | 修改管理页面 | 已完成 | 页面可刷新并选择 Gen-O 用户 |
| 5 | 启动项目 | 已完成 | Genesis、Gen-O、管理端和统一入口正常运行 |
| 6 | 测试接口和页面 | 已完成 | 接口返回正确，浏览器操作通过并截图 |
| 7 | 提交代码 | 已完成 | Gen-B `00a5681`，Gen-O `fd6bb2c` |
| 8 | 写报告 | 已完成 | `records/reports/20260714-REPORT-geno-live-user-mapping.md` |

### 6. 当前进度

当前做到哪一步：

- 进行中：无，本任务已完成。
- 已完成：用户目录接口、实时读取、首次自动关联、管理页面、本地浏览器联调、提交和报告。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] Gen-O 后端测试
- [x] Genesis 后端测试
- [x] 管理端构建
- [x] 登录流程
- [x] 权限管理页面
- [x] Gen-O SSO 关键接口

测试结果：

- Gen-O：用户目录和原有 SSO 共 4 个测试通过，存在项目既有 Pydantic/pytest 警告。
- Genesis：15 个测试通过，0 失败。
- 管理端：`npm run build` 通过，存在项目既有大包 warning。
- 真实接口：Genesis 登录成功，实时读取 Gen-O 用户返回 `code=200`、1 个用户；直接无密钥访问 Gen-O 目录被拒绝。
- 浏览器：从 `9100/login` 登录管理端，进入 `/genb/genesis-access`，刷新按钮、成功提示和 Gen-O 用户下拉框正常；相关接口均为 200，控制台 0 错误。
- 截图：`D:\default\Documents\genesis-geno-local-logs\genesis-access-geno-user-select.png`。

### 8. 风险和遗留问题

实时读取依赖 Gen-O 服务在线；当 Gen-O 不可用时，管理员仍能查看现有映射和权限，但不能刷新或选择新的 Gen-O 用户。用户名不唯一或没有同名账号时不会自动关联，必须由管理员选择，避免错误登录。管理端仓库当前没有可用 ESLint 配置，因此只执行了生产构建和浏览器验收，没有把 ESLint 标记为通过。

---

## 任务：区分本地与服务器的管理端跳转

### 1. 背景

本地从 `9100/login` 登录管理端后会跳到 `9100/genb/dashboard`。服务器由 Nginx 正确转发该路径，但本地客户端 Vite 没有 `/genb` 代理，导致业务客户端接管管理端路径并显示空白。

### 2. 目标

本地登录后继续使用同一 Origin 保留登录态，同时把 `/genb/` 页面交给 `9000` 管理端；服务器仍使用原有 Nginx 路由。

### 3. 范围

本次要做：

- 为客户端本地 Vite 增加可配置的管理端代理。
- 增加环境变量示例，写清本地和服务器的职责区别。
- 验证登录后进入管理端并能访问受保护接口。

本次不做：

- 不把 Token 放进 URL。
- 不降低管理接口权限。
- 不修改服务器 Nginx 或部署服务器。

### 4. 完成标准

- [x] 本地 `9100/genb/dashboard` 显示管理端页面。
- [x] 本地 `9100/genb/genesis-access` 显示统一门户权限页。
- [x] 登录 Token 保留在 `9100` Origin，管理接口不再返回 403。
- [x] 生产构建仍使用 `/genb/`，不写死本地 `9000`。
- [x] 客户端构建和浏览器登录流程通过。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 复现并确认路由原因 | 已完成 | 9100 返回业务客户端 HTML，接口无 Token 返回 403 |
| 2 | 修改本地代理和环境说明 | 已完成 | Vite 增加 `/genb` 代理和 `.env.example` |
| 3 | 重启客户端并测试登录 | 已完成 | 浏览器从登录页进入管理端并加载 2 个用户 |
| 4 | 构建和回归检查 | 已完成 | 16 个测试和生产构建通过 |
| 5 | 提交和写报告 | 已完成 | Gen-B `d04dc6c`，报告已生成 |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：本地代理、环境说明、服务重启、登录回归、构建、提交和报告。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] 管理员登录
- [x] 管理端 Dashboard
- [x] Genesis 权限页
- [x] 管理接口认证
- [x] 客户端生产构建

测试结果：

修复前 `9100/genb/dashboard` 返回业务客户端 HTML；修复后返回管理端 HTML。Playwright 从 `9100/login` 选择管理端并登录，最终进入 `9100/genb/dashboard`，Token 保留在同一 Origin；继续进入 `9100/genb/genesis-access` 后管理接口返回 200，显示 2 个用户，控制台 0 错误。客户端 5 个测试文件、16 个测试全部通过，生产构建通过且产物不包含本地 `9000` 地址。

### 8. 风险和遗留问题

- 本地代理依赖 `9000` 管理端先启动；未启动时应明确表现为代理连接失败，而不是回退到业务客户端空白页。
- 服务器仍需保持 Nginx 对 `/genb/` 的现有转发规则。

## 任务：增加 Genesis 用户与平台权限管理页面

### 1. 背景

目前 Genesis 用户的 Gen-O 映射和访问授权只能通过数据库或接口手工维护，容易填错外部用户 ID，也无法直观看到某个用户是否因映射、用户授权或角色授权而解锁平台。

### 2. 目标

管理员可以在 Gen-B 管理端查看统一门户用户，并在一个页面里维护用户的平台账号映射和用户级访问权限。

### 3. 范围

本次要做：

- 增加 Genesis 用户与平台权限查询、保存接口。
- 展示用户基础信息和 Gen-C、Gen-O、Gen-B 的映射及授权状态。
- 支持搜索、刷新、同步 Gen-B 用户。
- 支持维护外部用户 ID、外部用户名、映射状态和用户级访问开关。
- 增加管理端独立菜单和页面。
- 保持真实 SSO 密钥、本地数据库和回调配置不进入 Git。

本次不做：

- 不在浏览器页面展示或修改 SSO 共享密钥。
- 不管理 Gen-O 自己的密码、角色或账号启停。
- 不修改角色级平台授权。
- 不部署服务器。

### 4. 完成标准

- [x] 管理员可以查询和搜索 Genesis 用户。
- [x] 页面可以清楚区分账号映射、用户授权和角色继承授权。
- [x] 管理员可以保存平台外部账号映射。
- [x] 管理员可以开启或撤销用户级平台访问权。
- [x] 开启访问权时必须存在有效映射。
- [x] 非管理员不能调用管理接口。
- [x] 原有统一登录和其他管理端页面没有损坏。
- [x] 已完成后端测试、前端构建和页面测试。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 明确接口和组件边界 | 已完成 | DTO、服务和组件职责已拆分 |
| 2 | 编写后端服务测试 | 已完成 | 测试先因缺少实现而失败 |
| 3 | 实现管理接口 | 已完成 | 后端 12 个测试通过 |
| 4 | 实现管理端页面 | 已完成 | 页面可查询、编辑和保存 |
| 5 | 构建和浏览器测试 | 已完成 | 构建、接口、真实 Chrome 页面通过 |
| 6 | 审查、提交和写报告 | 已完成 | Gen-B `b874789`，报告已生成 |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：管理接口、独立页面、权限规则、测试、审查和本地提交。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] 后端单元测试
- [x] 后端构建
- [x] 管理端构建
- [x] 用户查询
- [x] 映射保存
- [x] 用户授权与撤销
- [x] 浏览器页面

测试结果：

后端 12 个测试通过，其中新管理服务 5 个测试覆盖管理员校验、状态区分、无映射拒绝授权、直接授权和撤销后保留角色授权。管理端生产构建通过。真实 Chrome 打开 `/genb/genesis-access`，显示 2 个用户；编辑 `admin` 的 Gen-O 映射并原值保存返回 200，成功提示和弹窗关闭正常，控制台 0 错误。仓库缺少 ESLint 配置，因此定向 ESLint 无法执行，未为此增加无关配置。

### 8. 风险和遗留问题

- 角色级授权可能让用户在撤销直接授权后仍可访问，页面必须明确显示“角色继承”，避免管理员误判。
- 外部用户 ID 必须由目标平台提供，Genesis 不应自动猜测或创建目标平台账号。
- 管理页第一版不修改角色级授权；需要批量按角色开通时应增加独立的角色授权页面，不能复用用户直接授权开关。

## 任务：完成本地 Genesis 与 Gen-O 统一登录联调

### 1. 背景

统一登录代码已经完成，但当前 Gen-O 没有启动，Genesis 后端仍是修改前的旧进程，`admin` 也尚未配置 Gen-O 映射和授权，因此本地还不能实际体验自动登录。

### 2. 目标

在本机启动完整环境，让 `admin` 从 Genesis 点击 Gen-O 后可以直接进入 Gen-O，不需要再次输入密码。

### 3. 范围

本次要做：

- 配置并启动本地 Gen-O 前后端。
- 重启 Genesis 后端加载最新统一登录代码。
- 为 `admin` 建立 Gen-O 用户映射和访问授权。
- 通过接口和浏览器验证完整登录流程。
- 记录本地配置、验证结果和遗留问题。

本次不做：

- 不部署或修改线上服务器。
- 不为其他用户批量开通 Gen-O。
- 不推送未确认的代码提交。

### 4. 完成标准

- [x] Gen-O 前后端可以在本地访问。
- [x] Genesis 后端已加载新的 SSO 接口。
- [x] `admin` 在 Gen-O 中有启用状态的对应账号。
- [x] `admin` 在 Genesis 中有有效映射和 Gen-O 授权。
- [x] 从 Genesis 点击 Gen-O 可以自动进入 Gen-O 首页。
- [x] 原有 Gen-O 登录仍然可用。
- [x] 已完成接口和页面测试。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 核对数据库、账号和启动配置 | 已完成 | 已确认 Genesis 服务器库和 Gen-O 本地 SQLite |
| 2 | 配置本地 SSO 参数 | 已完成 | 两端共享密钥一致，密钥文件已被 Git 忽略 |
| 3 | 配置 admin 映射和授权 | 已完成 | 数据库查询确认映射和用户授权均为 ACTIVE |
| 4 | 启动和重启服务 | 已完成 | 9100、8581、5173、8000 均正常监听 |
| 5 | 测试接口和页面 | 已完成 | 浏览器自动进入 Gen-O `/overview` |
| 6 | 更新报告 | 已完成 | `records/reports/20260713-REPORT-genesis-geno-local-debug.md` |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：本地配置、`admin` 映射与授权、服务启动、接口测试和浏览器端到端验收。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] Genesis 后端接口
- [x] Gen-O 后端接口
- [x] Genesis 登录流程
- [x] Gen-O 自动登录
- [x] Gen-O 原生登录

测试结果：

Genesis `admin` 登录通过，Gen-O 卡片返回 `mapped=true`、`granted=true`、`unlocked=true`；Ticket 签发和交换返回 200；Gen-O profile 返回启用的 `admin/admin`；原生密码登录返回 200。Playwright 使用真实 Chrome 从 Genesis 点击 Gen-O 后进入 `http://127.0.0.1:5173/overview`，页面控制台 0 错误。

### 8. 风险和遗留问题

- 本地共享密钥只能放在进程环境变量或被 Git 忽略的本地配置中，不能提交仓库。
- Genesis 当前配置指向服务器 PostgreSQL；用户已于 2026-07-13 明确允许本次联调连接该服务器数据库。本次只修改 `admin` 的 Gen-O 映射、授权及必要的平台回调配置，写入前后均需查询确认。
- Genesis 运行时使用干净构建后复制到 `D:\default\Documents\genesis-geno-local-runtime` 的独立 JAR，避免仓库中旧 `target/classes` 与新源码混用。

## 任务：接入 Genesis 与 Gen-O 统一登录

### 1. 背景

Gen-B 已经可以从 Genesis 门户免二次登录进入，但 Gen-O 目前仍只显示为锁定卡片。Gen-O 已有完整代码和自己的账号密码登录，如果不完成接入，用户仍需在两个系统分别登录，统一门户无法形成三平台接入样板。

### 2. 目标

用户登录 Genesis 后，点击已授权的 Gen-O，可以安全进入现有 Gen-O，不需要再次输入 Gen-O 密码；Gen-O 原登录继续可用。

### 3. 范围

本次要做：

- 拉取 Gen-O `dev` 最新代码并基于最新版本开发。
- Genesis 发放和校验短时、一次性 Gen-O ticket。
- Gen-O 校验 ticket、匹配已有用户并签发自己的登录凭证。
- Gen-O 前端接收 callback，建立现有登录态后进入首页。
- Genesis 门户点击 Gen-O 时申请 ticket 并跳转。
- 为新增安全边界和兼容原因添加详细中文注释。
- 完成测试、构建、文档、报告和 Git 提交。

本次不做：

- 不删除或替换 Gen-O 原账号密码登录。
- 不允许 Genesis token 直接成为 Gen-O token。
- 不自动创建无法映射的 Gen-O 用户。
- 不接入 Gen-C。
- 不部署服务器，除非用户后续明确要求。

### 4. 完成标准

满足下面这些条件，才算完成：

- [x] Gen-O `dev` 已快进拉取到最新 `origin/dev`。
- [x] 有映射和授权的 Genesis 用户可以申请 Gen-O 一次性 ticket。
- [x] ticket 只能校验一次，过期、错平台或错误客户端不能使用。
- [x] Gen-O 只允许已有且启用的映射用户通过 SSO。
- [x] Gen-O 使用自己的 JWT，不复用 Genesis token。
- [x] Gen-O 原登录、注册和密码修改功能没有被破坏。
- [x] Genesis 门户可以跳转到 Gen-O callback。
- [x] 后端测试、前端类型检查和构建通过。
- [x] 新增代码写明为什么增加以及安全原因。
- [x] 已完成代码审查、文档、报告和 Git 提交。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 拉取最新代码并理解认证结构 | 已完成 | Git 状态、影响范围说明 |
| 2 | 实现 Genesis ticket | 已完成 | Java 接口测试 |
| 3 | 实现 Gen-O SSO exchange | 已完成 | Python 接口测试 |
| 4 | 接入两个前端 | 已完成 | 类型检查、页面路由测试 |
| 5 | 完整测试和安全审查 | 已完成 | 测试、构建、diff 检查 |
| 6 | 更新文档和报告 | 已完成 | 文档文件检查 |
| 7 | 提交代码 | 已完成 | Gen-B `a0e7665`、Gen-O `ef86416` |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：代码、测试、构建、审查、文档和两个本地提交。
- 阻塞：线上启用需要正式 callback、共享密钥、用户映射、平台授权和部署；本次未获部署授权，因此未执行。

### 7. 验收记录

实际测试了什么：

- [x] Genesis 后端测试
- [x] Gen-O 后端测试
- [x] Gen-B 客户端构建
- [x] Gen-O 前端测试和构建
- [x] 原生登录回归
- [x] SSO 成功链路
- [x] ticket 重放和异常链路

测试结果：

Genesis 7 个测试通过；Gen-O 认证与 SSO 10 个测试通过；两个前端构建通过；新增 Gen-O 前端文件 ESLint 通过；国际化 key 0 缺失。全仓库 ESLint 仍有大量拉取前已有问题，未在本任务中批量修改。

### 8. 风险和遗留问题

- Gen-O 拉取了 111 个新提交，本次必须只改 SSO 直接相关文件，不能顺手调整同事的国际化、推理或部署代码。
- Genesis 与 Gen-O 的服务端密钥和正式 callback URL 需要部署时配置；代码中不得写死真实密钥。

## 任务：统一任务报告模板

### 1. 背景

现有 `records/reports/README.md` 只规定了简版报告内容，导致新报告没有使用用户要求的八段式任务模板。如果不修正，后续报告结构仍会不一致。

### 2. 目标

把用户指定的八段式结构设为统一任务报告模板，并修正刚生成的全局规则设置报告。

### 3. 范围

本次要做：

- 更新报告模板入口。
- 按新模板改写本轮报告。
- 复核八个章节和验收内容。

本次不做：

- 不批量改写全部历史报告。
- 不修改项目代码。

### 4. 完成标准

- [x] `records/reports/README.md` 包含用户指定的八段式模板。
- [x] 本轮任务报告已按新模板改写。
- [x] 模板和报告均完成结构检查。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 检查现有模板和报告 | 已完成 | 已读取两个文件 |
| 2 | 更新统一模板 | 已完成 | 检查八个章节 |
| 3 | 改写本轮报告 | 已完成 | 对照模板检查 |
| 4 | 完成验收 | 已完成 | 文本检索和文件复核 |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：确认遗漏原因、更新统一模板、改写本轮报告并完成结构检查。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] 模板章节检查
- [x] 本轮报告章节检查
- [x] 文件可读取检查

测试结果：

全部通过。模板和本轮报告均可读取，且都完整包含第 1 至第 8 节。

### 8. 风险和遗留问题

历史报告暂不批量改写；若需要统一历史文档，应单独执行并逐份核对内容。

## 任务：设置 Codex 全局语言与安装下载规则

### 目标

读取旧聊天交接文件，并确保以下规则写入 Codex 实际读取的全局指令：除专业内容外使用中文；可选时优先在 D/E 盘安装下载；所有安装下载写入指定记录文件。

### 成功标准

- [x] 已读取 `C:\Users\szhar\AppData\Local\Temp\GENB_CODEX_HANDOFF_20260713.md`。
- [x] `C:\Users\szhar\.codex\AGENTS.md` 明确写入三条全局规则和记录文件完整路径。
- [x] `D:\default\Documents\install_download_log.md` 存在，并明确名称、用途、下载位置、安装位置、时间字段。
- [x] 已复核文件内容并写任务报告。

### 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 读取交接和现有全局配置 | 已完成 | 文件内容检查 |
| 2 | 补全全局规则 | 已完成 | 重新读取 `AGENTS.md` |
| 3 | 建立或规范安装下载记录文件 | 已完成 | 检查文件和字段 |
| 4 | 复核并写报告 | 已完成 | 文件检查 |

### 当前进度

- 已完成：全局规则文件明确指定记录文件完整路径；安装下载记录文件保留历史内容并补全统一新格式；任务报告已写入。
- 验证：重新读取两个目标文件，三条规则和五个必填字段均存在。
- 阻塞：无。

### 下一步

后续每次安装或下载时，按新模板追加记录。

## 任务：修复多语言导致智能体列表超时

### 1. 背景

后端多语言第一版上线后，页面访问智能体市场出现 `timeout of 12000ms exceeded`。之前已经约定普通列表查询不能实时查 Docker/进程状态，只能使用启动时或刷新状态时写入表里的缓存状态。

当前代码检查显示普通查询没有实时查 Docker/进程状态，但多语言翻译服务对每个智能体逐字段查询 `i18n_texts`，远程库下产生大量查询，导致列表接口变慢。

### 2. 目标

修复智能体列表接口超时问题，保持正常列表只读缓存状态，并让英文展示字段仍然可用。

### 3. 范围

本次要做：

- 检查普通列表是否实时查状态。
- 修复多语言翻译 N+1 查询。
- 验证接口响应时间。
- 打开页面查看是否仍超时。
- 提交修复。

本次不做：

- 不改客户端页面样式。
- 不改 Docker 状态刷新策略。
- 不部署服务器，除非后续明确要求。

### 4. 完成标准

- [ ] 普通列表查询不实时查 Docker/进程状态。
- [ ] 英文智能体列表接口不再超时。
- [ ] 客户端页面可以打开智能体市场。
- [ ] `mvn test` 通过。
- [ ] 已提交代码。
- [ ] 已写报告。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 检查状态查询链路 | 已完成 | `agentService.search()` 不调用 Docker/进程状态 |
| 2 | 定位超时原因 | 已完成 | 日志确认大量 `i18n_texts` 查询 |
| 3 | 修复翻译查询 | 已完成 | 批量加载翻译，减少 SQL |
| 4 | 后端构建 | 已完成 | `mvn test` |
| 5 | 接口验证 | 已完成 | catalog 响应不超时 |
| 6 | 页面验证 | 已完成 | 浏览器打开智能体市场 |
| 7 | 提交和报告 | 进行中 | Git 提交 + records 报告 |

### 6. 当前进度

- 进行中：提交和报告。
- 已完成：确认普通列表不实时查 Docker/进程状态；定位超时来自多语言翻译 N+1 查询；已改为批量加载翻译；接口和页面验证通过。
- 阻塞：无。

### 7. 验收记录

- [x] 后端构建
- [x] 智能体目录接口
- [x] 客户端页面

测试结果：

- `mvn test` 通过。
- 远程库下 `GET /api/v1/client/agents/catalog` 带 `X-Locale: en-US` 返回 80 条数据，耗时约 0.995 秒。
- 浏览器打开 `http://localhost:9100/agent-factory`，耗时约 3.237 秒，无 `timeout of 12000ms exceeded`。
- 页面截图：`records/reports/assets/20260713-agent-factory-i18n-timeout-fix.png`。

### 8. 风险和遗留问题

远程库下智能体列表本身还存在全量查询和内存分页问题，本次先修复多语言引入的额外慢查询。后续如仍慢，需要把 `AgentService.search()` 改成数据库分页和条件查询。

---

## 任务：后端和数据库支持英文版多语言

### 1. 背景

Gen-B 客户端英文版由同事负责，但后端接口和数据库里仍有大量中文内容，例如登录提示、权限提示、智能体名称、智能体描述、业务分类、Genesis 平台描述和锁定原因。如果后端和数据库不支持英文，前端切到英文后仍会出现大量中文，英文版无法完整交付。

### 2. 目标

让后端接口和数据库内容支持中英文返回。用户选择英文后，前端请求接口时带上语言标识，后端返回英文提示、英文智能体信息、英文平台信息；没有英文翻译的数据回退中文，不影响现有中文版本。

### 3. 范围

本次要做：

- 梳理后端接口和数据库中的中文来源。
- 给后端增加语言识别能力。
- 给统一接口返回增加 `messageKey`，保留原有 `message`。
- 新增数据库翻译表，用于智能体、平台、角色等业务数据翻译。
- 改造第一批核心接口，让它们能按语言返回中文或英文。
- 增加初始化/迁移脚本。
- 补充后端和数据库英文版接入文档。
- 做本地接口验证。

本次不做：

- 不做客户端页面英文切换。
- 不做管理端页面英文切换。
- 不改 Gen-C、Gen-O 代码。
- 不做 SSO ticket 改造。
- 不部署服务器，除非后续明确要求。

### 4. 完成标准

- [ ] 前端可以通过 `X-Locale: en-US` 请求英文接口。
- [ ] 不传语言时，接口默认返回中文，现有页面不受影响。
- [ ] 登录、用户信息、智能体列表、智能体市场、Genesis 平台接口可以返回英文提示或英文业务内容。
- [ ] 数据库有统一翻译表，不需要给每张表乱加英文列。
- [ ] 保留原中文名称，并在返回结果中新增英文/本地化展示字段。
- [ ] 状态、枚举、接口提示由后端统一翻译。
- [ ] 没有英文翻译的数据可以回退中文。
- [ ] 原有中文接口没有坏。
- [ ] 已完成后端构建或测试。
- [ ] 已完成关键接口测试。
- [ ] 已写任务报告到 `records/reports/`。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 理解现有代码和文档 | 已完成 | 写出影响范围 |
| 2 | 设计翻译表和语言规则 | 已完成 | 写出 SQL 和回退规则 |
| 3 | 修改后端语言识别逻辑 | 已完成 | `X-Locale` / `Accept-Language` 能被识别 |
| 4 | 修改统一返回结构 | 已完成 | `Result` 返回 `messageKey` 且兼容 `message` |
| 5 | 新增后端消息字典 | 已完成 | 登录成功/失败等消息可中英文返回 |
| 6 | 新增数据库翻译服务 | 已完成 | 能按实体、字段、语言查询翻译 |
| 7 | 改造核心接口 | 已完成 | 智能体、Genesis 平台等接口可返回英文 |
| 8 | 新增迁移脚本和初始数据 | 已完成 | 本地数据库可执行，重复执行不报错 |
| 9 | 启动项目 | 已完成 | 后端正常运行 |
| 10 | 测试接口 | 已完成 | 中英文接口返回正确 |
| 11 | 提交代码 | 已完成 | Git 有提交记录 |
| 12 | 写报告 | 已完成 | `records/reports/` 有记录 |

### 6. 当前进度

- 进行中：无。
- 已完成：已确认英文翻译由我完成；保留中文原字段，新增英文/本地化展示字段；后端统一翻译；不处理 Gen-C/Gen-O；后端代码、SQL、文档、本地接口验证、代码提交和报告已完成。
- 阻塞：无。

### 7. 验收记录

- [x] 后端构建
- [x] 登录流程
- [x] 用户信息接口
- [x] 智能体列表接口
- [x] 智能体市场接口
- [x] Genesis 平台接口
- [x] 中文默认返回
- [x] 英文请求返回
- [x] 无翻译回退中文

测试结果：

- `mvn test` 通过。
- 本地库执行 `i18n_texts_init.sql` 成功，插入/更新 37 条基础英文翻译。
- `POST /api/v1/auth/login` 默认返回 `登录成功`，带 `X-Locale: en-US` 返回 `Signed in successfully`。
- `GET /api/v1/client/agents/catalog` 带 `X-Locale: en-US` 返回 `nameEn`、`displayName`、`businessAttributeLabelEn`、`displayBusinessAttribute` 等字段。
- `GET /api/v1/genesis/platforms/my` 带 `X-Locale: en-US` 返回英文平台描述和英文锁定原因。
- 本地 `create-genB` 已提交：`26c76f9 feat: add backend i18n support`。

### 8. 风险和遗留问题

客户端同事需要在请求中传 `X-Locale` 或 `Accept-Language`，否则后端默认中文。数据库已有业务内容如智能体名称和描述需要人工校对英文，第一版由我先给非中式英文翻译。

---

## 任务：同步同事状态到个人功能分支

### 1. 背景

公司 GitLab 的 `create-genB` 已经更新到已验证测试分支 `2f10ded`。你的个人分支 `feature/genesis-client` 仍停留在 `74ce9c9`，需要同步同事分支当前状态。

### 2. 目标

把 `feature/genesis-client` 快进到 `create-genB` 当前状态，让你的分支也包含同事提交和管理端验证修复。

### 3. 范围

本次要做：

- 拉取公司远端最新分支。
- 确认 `feature/genesis-client` 可以快进到 `create-genB`。
- 更新并推送 `feature/genesis-client`。
- 做远端状态确认。

本次不做：

- 不改业务代码。
- 不重新部署服务器。
- 不重新执行完整构建测试。

### 4. 完成标准

- [x] 已确认 `feature/genesis-client` 是 `create-genB` 的祖先。
- [x] 本地 `feature/genesis-client` 指向 `2f10ded`。
- [x] 远端 `company/feature/genesis-client` 指向 `2f10ded`。
- [x] 本地 `gen-b` 工作区干净。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 拉取远端分支 | 已完成 | `git fetch company` |
| 2 | 检查分支关系 | 已完成 | `git log` 显示个人分支是 `create-genB` 祖先 |
| 3 | 快进个人分支 | 已完成 | `git merge --ff-only company/create-genB` |
| 4 | 推送个人分支 | 已完成 | `git push company feature/genesis-client` |
| 5 | 状态确认 | 已完成 | `git ls-remote`、`git status` |

### 6. 当前进度

- 进行中：无。
- 已完成：远端拉取、分支关系确认、本地快进、推送和远端状态确认。
- 阻塞：无。

### 7. 验收记录

- [x] 分支状态
- [x] 远端提交

测试结果：

- 本地 `feature/genesis-client` 已从 `74ce9c9` 快进到 `2f10ded`。
- 远端 `company/feature/genesis-client` 已从 `74ce9c9` 更新到 `2f10ded`。
- 远端 `company/create-genB`、`company/codex/company-genb-sync`、`company/feature/genesis-client` 当前均指向 `2f10ded`。
- 本地 `gen-b` 工作区干净。

### 8. 风险和遗留问题

本次只同步分支指针，不新增代码修改。由于 `feature/genesis-client` 是 `create-genB` 当前提交的祖先，已通过快进更新完成，不产生合并提交。未重新执行构建和页面测试，沿用上一轮 `codex/company-genb-sync` 的完整验证结果。

---

## 当前任务：Gen-B 后端与数据库国际化计划

### 目标

补充一份聚焦后端返回和数据库内容的英文版改造精准计划，明确哪些中文由前端翻译、哪些由后端 messageKey 管理、哪些数据库内容需要新增翻译表，以及代码改造范围。

### 成功标准

- 明确“不大面积新增 `xxx_en` 字段”的数据库原则。
- 明确 `agents`、`genesis_platforms`、`roles` 等表的处理方式。
- 给出新增表 SQL、后端 DTO/Service/Controller 改造点。
- 给出兼容现有中文接口的分阶段实施方案。
- 更新文档索引，便于后续开发直接按文档执行。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 扫描现有前端文案表和后端中文来源 | 已完成 | `rg` / 文件读取 | 已确认中文来源包含 `Result.message`、异常、Genesis 锁定原因、种子数据、数据库内容。 |
| 编写后端与数据库 i18n 计划文档 | 已完成 | 文件存在和内容检查 | 已新增 `docs/requirements/BACKEND_DATABASE_I18N_PLAN.md`。 |
| 更新文档索引 | 已完成 | `PROJECT_INDEX.md`、`docs/INDEX.md` | 已同步项目索引和文档索引。 |
| 生成任务报告 | 已完成 | `records/reports/` | 已新增 `records/reports/20260710-REPORT-backend-database-i18n-plan.md`。 |

### 最近验证

- 已读取 `docs/requirements/CLIENT_I18N_COPY_MAP.md`，确认其范围只覆盖客户端前端固定文案。
- 已读取 `Result.java`，当前统一响应只有 `code/message/data`，默认中文 `操作成功`。
- 已读取 `Agent.java`、`ClientAgentVO.java`、`GenesisPlatformVO.java`，确认智能体名称/描述/分类、平台名称/描述/锁定原因是英文版重点。
- 已新增后端与数据库国际化精准计划文档。
- 已更新 `PROJECT_INDEX.md`、`docs/INDEX.md`、`records/RECORDS_INDEX.md`。
- 已新增任务报告。

### 下一步

如开始实施，按 `BACKEND_DATABASE_I18N_PLAN.md` 第一阶段执行：新增 `i18n_texts`、`Result.messageKey`、VO `localized` 字段和客户端 `X-Locale`。

---

## 当前任务：公司 GitLab gen-b 对接、合并与验证

### 目标

将本地 `D:\code\opencode\genb\gen-b` 与公司内部 GitLab `huanglinghu/gen-b` 的 `create-genB` 分支对接，整理并提交本地有效改动，合并同事中英文版本提交，然后验证后端接口、客户端页面和管理端页面是否正常。

### 成功标准

- 公司 GitLab remote 配置可用。
- 生成物、依赖缓存、压缩包不进入提交。
- 本地 Genesis/SSO 有效源码被提交。
- 公司 `create-genB` 中英文管理端改动被合并。
- 后端测试或启动验证通过。
- 客户端和管理端构建通过。
- 本地浏览器验证登录、Genesis 门户、客户端主页、管理端页面基本可用。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 配置并测试公司 GitLab SSH | 已完成 | `ssh -T`、`git ls-remote` | SSH 端口 `2424`，用户 `@shizhenhua`。 |
| fetch `company/create-genB` | 已完成 | `git fetch company create-genB` | 远端提交 `25bc6da feat:中英文补全`。 |
| 克隆 Gen-O | 已完成 | `git clone`、`git status` | 已到 `D:\code\opencode\genb\gen-o`。 |
| 清理生成物和依赖缓存变更 | 已完成 | `git status --short` | `gen-b` 工作区只剩源码变更，构建缓存已恢复。 |
| 提交本地 Genesis/SSO 有效源码 | 已完成 | `git commit` | 已提交 `0c6c7d3 feat: add genesis portal sso`。 |
| 合并 `company/create-genB` | 已完成 | `git merge` / 冲突检查 | 已生成 merge commit `0917697`，无冲突。 |
| 后端验证 | 已完成 | Maven 测试/启动/API | `mvn test` 通过，核心接口本地联调通过。 |
| 客户端验证 | 已完成 | build + 浏览器 | `npm run build` 通过，登录页和门户页浏览器验证通过。 |
| 管理端验证 | 已完成 | build + 浏览器 | 已修复 Dashboard reactive warning 和 i18n 缺失 key，复测控制台 warning 为 0。 |
| 更新报告 | 已完成 | `records/reports/` | 已新增本次合并与验证报告。 |

### 最近验证

- `gen-b` 公司 remote：`ssh://git@47.116.69.17:2424/huanglinghu/gen-b.git`。
- `gen-o` 公司 remote：`ssh://git@47.116.69.17:2424/chentao/gen-o.git`。
- 已完成公司 `create-genB` 合并和主要接口/页面验证。
- 后端 `mvn test` 通过；客户端和管理端 `npm run build` 通过。
- 浏览器验证：Genesis 门户登录后通过 token exchange 进入 Gen-B；客户端 test_user 登录和智能体市场可用；管理端 Dashboard/智能体中心可用。
- 已修复管理端 Dashboard KPI 图标 reactive warning。
- 已修复管理端缺失 i18n key：`dashboard.module2.*`、`agents.tag`、`agents.version`、`agents.dockerStatus`。

### 下一步

提交管理端修复；如需要同步到公司 GitLab，再 push `codex/company-genb-sync`。

---

## 当前任务：Genesis 统一门户联调

### 目标

继续联调 Genesis 统一门户第一版：启动新后端、新前端，执行 Gen-B 用户同步，验证 Genesis 登录、平台状态和 `/portal/login` 页面。

### 成功标准

- 后端使用最新代码启动成功。
- 前端开发服务启动成功。
- 管理员登录后可调用 `POST /api/v1/genesis/sync/gen-b-users`。
- Genesis 用户可登录。
- `/api/v1/genesis/platforms/my` 返回 Gen-B 解锁，Gen-C/Gen-O 锁定。
- 浏览器打开 `/portal/login` 可看到门户页面并完成登录/解锁基本流程。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 检查并重启后端 | 已完成 | 端口/日志/API | 后端已在 8581 启动。 |
| 启动前端 | 已完成 | Vite URL | `9100` 被占用，前端已启动在 `9101`。 |
| 调用同步和接口联调 | 已完成 | HTTP 返回 | 已完成 Gen-B 用户同步和平台状态接口验证。 |
| 浏览器页面验证 | 已完成 | 浏览器截图/交互 | 已验证门户登录、锁定提示、Gen-B 进入客户端。 |
| 更新报告 | 已完成 | records | 已更新联调报告。 |

### 最近验证

- 后端已启动：`http://localhost:8581/api`。
- 前端已启动：`http://localhost:9101/portal/login`。
- `POST /api/v1/genesis/sync/gen-b-users` 返回同步成功：用户 2、角色 3、平台 3、映射 2、授权 2。
- `GET /api/v1/genesis/platforms/my` 返回 Gen-B 解锁，Gen-C/Gen-O 锁定。
- 浏览器验证发现：门户登录后点击 Gen-B 会跳到 `/login?redirect=/my-agents`，原因是门户 token 未同步到客户端现有 `genb-client-token`，已开始修正。
- 已修正门户 token 同步问题。
- 浏览器重测：点击 Gen-B 已直接进入 `http://localhost:9101/my-agents`。
- 接口补测：`test_user/test123` 可登录 Genesis，Gen-B 解锁，Gen-C/Gen-O 锁定。
- 前端 `npm run build` 成功。

### 下一步

等 Gen-C / Gen-O 提供用户表和入口后，继续做映射导入、平台授权和 SSO ticket 方案。

---

## 当前任务：Genesis 统一门户视觉与登录动效优化

### 目标

以参考图为主视觉，以 `genesis-engine-sso.html` 的登录后通道解锁效果为交互参考，优化 `/portal/login` 的背景、登录框、登录过程和平台卡片动效。

### 成功标准

- 背景更接近参考图：深蓝科技底色、粒子波浪、发光层次。
- 登录框更接近参考图：玻璃拟态、输入框聚焦发光、按钮有认证状态。
- 登录后平台通道依次点亮，锁定/可访问状态明显。
- 保持原有接口、路由、登录逻辑不变。
- 前端构建通过，并用浏览器验证页面可访问和登录流程。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 对比参考图、HTML 原型和当前 Vue 组件 | 已完成 | 文件读取/图片查看 | 已确认主要差异在背景强度、玻璃层、登录反馈和解锁动效。 |
| 优化背景、登录框、平台卡样式 | 已完成 | 代码检查 | 已改门户前端组件。 |
| 构建验证 | 已完成 | `npm run build` | 构建通过，只有既有 chunk 体积警告。 |
| 浏览器验证 | 已完成 | `/portal/login` | 已验证登录前锁定、登录后 Gen-B 解锁。 |
| 更新报告 | 已完成 | records | 已新增视觉优化报告。 |

### 最近验证

- 已查看当前门户截图和参考图。
- 已读取 `genesis-engine-sso.html`。
- 已读取当前门户 Vue 组件。
- 已优化 `PortalWaveBackground.vue`、`PortalLoginForm.vue`、`PlatformGateList.vue`、`PortalLoginView.vue`。
- `npm run build` 通过。
- 浏览器验证：登录前平台锁定；登录后 Gen-C/Gen-O 锁定，Gen-B 解锁并显示“访问Gen-B”。
- 已新增 `records/reports/20260709-REPORT-genesis-portal-visual-polish.md`。

### 下一步

等待用户和设计同事确认视觉；如需要可继续微调 logo、卡片尺寸、背景亮度和动效节奏。

---

## 当前任务：Genesis 统一门户融合版重做与对比验收

### 目标

当前视觉版不通过。重新按参考图的页面结构和视觉质感，结合 `genesis-engine-sso.html` 的登录后解锁动效，做一版融合门户页，并截图对比参考图、HTML 原型和新版。

### 成功标准

- 页面第一眼更接近参考图，而不是当前版。
- 登录框、输入框、按钮有更完整的登录反馈。
- 平台入口保留参考图卡片结构，登录后有 HTML 原型的错峰解锁/点亮效果。
- 使用浏览器和电脑工具截图验证。
- 说明三者哪个更好看、各自优势在哪里。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 重做平台卡与登录动效 | 已完成 | 代码检查 | 去掉当前左侧总线，改为参考图卡片结构。 |
| 重做背景和登录面板 | 已完成 | 代码检查 | 已调整居中布局、输入框白底、粒子波浪。 |
| 构建验证 | 已完成 | `npm run build` | 构建通过，只有既有 chunk 体积警告。 |
| 浏览器/电脑截图验收 | 已完成 | 截图对比 | 浏览器已截图；Computer Use 当前因浏览器 URL 策略限制无法继续。 |
| 更新报告 | 未开始 | records |  |

### 最近验证

- 当前版被用户明确否定。
- 需要重新融合参考图和 HTML 原型。
- 已修复 input 点击/输入时浏览器白底和 autofill 白底问题。
- 已把页面舞台改为标题区 + 内容区垂直居中布局。
- 已增强背景中部发光波脊和粒子海。
- 浏览器实测：内容区 top=180、bottom=653，相比上一版更接近上下居中。
- 浏览器实测：输入前和输入后 input 背景均为 `rgba(5, 37, 60, 0.22)`，不是白底。
- 浏览器实测：登录后 Gen-C/Gen-O 锁定，Gen-B 解锁并显示“访问Gen-B”。
- `npm run build` 通过。

### 下一步

更新报告，并等待用户确认视觉是否继续微调。

---

## 当前任务：临时服务器约束日期化修正

### 目标

把“演示期间不要操作服务器”从长期硬性约束改为带具体日期的临时约束记录；当前 2026-07-08 下午演示冻结已过期，后续服务器操作按用户明确要求和部署风险流程执行。

### 成功标准

- 当前硬性约束不再写“今天下午有演示”。
- 部署/运维文档明确临时冻结必须写具体起止日期。
- 记录 2026-07-08 下午演示冻结已过期。
- 本次只改文档，不改业务代码。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 定位演示冻结长期表述 | 已完成 | `rg` 搜索 | 已定位 AGENTS、部署、运维等文档。 |
| 修改当前约束 | 已完成 | 文件内容检查 | 已删除过期长期约束。 |
| 新增变更记录 | 已完成 | 文件存在检查 | 已记录具体日期和规则。 |
| 验证 | 已完成 | `rg` 搜索 | 当前规则已改为具体日期；旧句只保留在历史说明中。 |

### 最近验证

- 已新增 `docs/changes/20260709-CHANGE-temporary-freeze-date-boundary.md`。
- 已更新 `AGENTS.md`、部署、运维、任务入口和架构相关文档。
- `rg` 验证：旧“今天下午有演示”只保留在历史变更说明和本任务说明中，不再作为当前硬性约束。

### 下一步

后续记录临时约束时，必须转换成具体年月日和起止时间。

---

## 当前任务：Genesis 统一门户第一版

### 目标

新增 Genesis 统一门户第一版：后端新增 Genesis 用户/平台/授权/映射体系和登录接口，前端新增 `/portal/login` 门户页；当前只同步 Gen-B 用户，登录后只解锁 Gen-B，Gen-C/Gen-O 保持锁定并提示联系管理员。

### 成功标准

- Gen-B 原 `/login` 保持不变。
- 新增 Genesis 后端表、同步接口、登录接口和平台状态接口。
- 同步 Gen-B 用户后，Genesis 登录可用。
- `/portal/login` 登录成功后不跳转，平台卡片依次点亮。
- 第一版只有 Gen-B 可点击，Gen-C/Gen-O 提示尚未开通。
- 新增对外接入文档。
- 完成后运行后端/前端构建或说明未能验证原因。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 新增 Genesis 后端实体/仓库/DTO/服务/接口 | 已完成 | 后端编译 | 已新增 Genesis 模块。 |
| 新增前端门户 API、类型、组件和路由 | 已完成 | 前端构建 | `/login` 不变，新增 `/portal/login`。 |
| 新增对外接入文档 | 已完成 | 文件存在检查 | 已新增 Gen-C/Gen-O 对接文档。 |
| 验证与记录报告 | 已完成 | build/test/report | 已完成编译、构建和报告。 |

### 最近验证

- 后端 `mvn test`：BUILD SUCCESS，当前无测试用例。
- 前端 `npm run build`：构建成功。
- 未启动后端和未浏览器联调，原因是当前 `application.yml` 指向远程数据库，避免误操作服务器数据。

### 下一步

切换到本地数据库配置后，调用 `POST /api/v1/genesis/sync/gen-b-users` 同步本地 Gen-B 用户，再做 `/portal/login` 浏览器联调。

---

## 当前任务：知识库检索效率优化

### 目标

优化当前工程知识库，让“随便说一个需求”时可以更快判断该读哪些文档、哪些代码必须复核、哪些历史记录可参考。

### 成功标准

- 新增文档状态说明，标明哪些文档可作为入口，哪些必须代码复核。
- 新增常见任务入口卡片，按需求类型列出必读文档、定向代码和验证方式。
- 新增 records 反向索引，按主题定位历史报告、计划、Bug、部署记录。
- 更新 `PROJECT_INDEX.md` 和 `docs/INDEX.md`。
- 本次只改文档，不改业务代码。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 新增文档状态说明 | 已完成 | 文件存在检查 | 已新增 `docs/DOC_STATUS.md`。 |
| 新增任务入口卡片 | 已完成 | 文件存在检查 | 已新增 `docs/TASK_ENTRYPOINTS.md`。 |
| 新增 records 反向索引 | 已完成 | 文件存在检查 | 已新增 `records/RECORDS_INDEX.md`。 |
| 更新索引和报告 | 已完成 | `PROJECT_INDEX.md`/records | 已新增本次报告。 |

### 最近验证

- 已新增 `docs/DOC_STATUS.md`。
- 已新增 `docs/TASK_ENTRYPOINTS.md`。
- 已新增 `records/RECORDS_INDEX.md`。
- 已新增 `records/reports/20260708-REPORT-knowledge-retrieval-optimization.md`。
- 已更新 `PROJECT_INDEX.md`、`docs/INDEX.md`、`records/README.md`。

### 下一步

后续收到需求时，优先按 `docs/TASK_ENTRYPOINTS.md` 选择文档和代码复核范围。

---

## 当前任务：接口契约、数据库明细、ER 和权限矩阵补充

### 目标

在已有后端接口文档、数据库文档、页面设计文档基础上，继续补充接口请求/响应结构、数据库字段明细、ER 关系和权限矩阵。

### 成功标准

- 新增 API 契约文档，覆盖客户端关键接口和管理端主要接口的入参/响应方向。
- 新增数据库字段明细文档，覆盖核心 Entity 的字段用途。
- 新增 ER/关系文档，说明用户、角色、权限、智能体、授权、申请、部署、监控之间关系。
- 新增权限矩阵文档，说明不同角色可访问页面和接口范围。
- 更新 `PROJECT_INDEX.md`。
- 本次只改文档，不改业务代码。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 扫描 Entity 字段和 Controller 方法 | 已完成 | `rg`/文件读取 | 已扫描 Controller、Entity、DTO。 |
| 扫描权限相关代码 | 已完成 | `rg` 搜索 role/permission | 已扫描 SecurityConfig、AuthService 和相关 Service。 |
| 新增 API 契约/数据库明细/ER/权限矩阵 | 已完成 | 文件存在检查 | 已新增 4 份文档。 |
| 更新索引和报告 | 已完成 | `PROJECT_INDEX.md`/records | 已新增本次报告。 |

### 最近验证

- 已新增 `docs/development/API_CONTRACTS.md`。
- 已新增 `docs/development/DATABASE_FIELDS.md`。
- 已新增 `docs/architecture/ER_RELATIONSHIP.md`。
- 已新增 `docs/security/PERMISSION_MATRIX.md`。
- 已新增 `records/reports/20260708-REPORT-api-db-permission-detail.md`。

### 下一步

后续建议导出真实 PostgreSQL DDL，并引入 OpenAPI 自动生成接口文档，避免人工文档漂移。

---

## 当前任务：工程知识库补全

### 目标

补全工程知识库中仍缺失的关键内容：后端接口文档、数据库表结构文档、客户端页面级设计文档、管理端页面级设计文档。

### 成功标准

- 后端接口文档覆盖主要 Controller、接口路径、用途和注意事项。
- 数据库文档覆盖核心实体/表、字段方向和关系。
- 客户端页面设计文档覆盖路由、页面职责、数据来源、状态和交互。
- 管理端页面设计文档覆盖路由、页面职责和模块边界。
- `PROJECT_INDEX.md` 挂载新增文档。
- 本次只改文档，不改业务代码。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 扫描后端接口和实体 | 已完成 | `rg` 搜索 Controller/Entity | 已扫描 Controller 和 Entity。 |
| 扫描客户端和管理端页面 | 已完成 | `rg` 搜索 router/views | 已扫描两个前端路由和 views。 |
| 新增四类文档 | 已完成 | 文件存在检查 | 已新增接口、数据库、客户端页面、管理端页面文档。 |
| 更新索引 | 已完成 | `PROJECT_INDEX.md` 可导航 | 已链接新增文档。 |

### 最近验证

- 已新增 `docs/development/BACKEND_API.md`。
- 已新增 `docs/development/DATABASE_SCHEMA.md`。
- 已新增 `docs/design/CLIENT_PAGE_DESIGN.md`。
- 已新增 `docs/design/CONSOLE_PAGE_DESIGN.md`。
- 已新增 `records/reports/20260708-REPORT-knowledge-base-completion.md`。

### 下一步

后续可继续补：接口请求/响应结构、真实 DDL、ER 图、权限矩阵。

---

## 当前任务：工程知识库增强

### 目标

把当前项目文档从“目录骨架”补强为可用的工程知识库：包含代码/文档统计、项目模块说明、设计文档、开发文档、部署文档、运维文档、PRD/需求文档，以及 records 下的过程记录。

### 成功标准

- 生成核心项目代码量、文档量、文件量统计。
- `docs/` 下的设计、开发、部署、运维、需求文档有实质内容，不只是占位。
- `records/` 下至少有本次计划和完成报告，后续任务有记录入口。
- `PROJECT_INDEX.md` 能导航到新增知识库内容。
- 本次只改文档，不改业务代码。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 统计代码量和文档量 | 已完成 | 生成统计文档 | 已新增 `context/code-statistics.md`。 |
| 补强设计/开发/部署/运维/需求文档 | 已完成 | 文件内容检查 | 已补强多个 docs 文档。 |
| 补充 records 计划和报告 | 已完成 | 文件存在检查 | 已新增 plan 和 report。 |
| 更新索引 | 已完成 | `PROJECT_INDEX.md` 可导航 | 已链接新增文档。 |

### 最近验证

- 已统计 5 个核心项目：代码 52,197 行，文档 2,469 行。
- 已新增工程知识库计划和报告。

### 下一步

后续建议继续补后端接口文档、数据库表结构文档、客户端页面级设计文档和管理端页面级设计文档。

---

## 当前任务：客户端英文版文案对照整理

### 目标

扫描 `gen-b/gen-b-client` 中所有前端用户可见中文文案，整理中文与英文对照表，供后续客户端英文版开发使用。

### 成功标准

- 覆盖 Vue 页面、组件、路由、store/API 错误提示中可见中文。
- 去重整理，保留上下文说明。
- 标出可能来自后端或数据表的动态文案，避免误认为前端硬编码。
- 本次只整理文案，不改客户端代码。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 扫描客户端源码中文 | 已完成 | `rg` 搜索中文字符 | 已排除测试文件，只扫运行代码和 `index.html`。 |
| 汇总中英文对照 | 已完成 | 人工整理去重 | 已生成 `docs/requirements/CLIENT_I18N_COPY_MAP.md`。 |
| 标注动态文案和后续建议 | 已完成 | 说明数据来源 | 已在文档末尾说明动态数据和 i18n 建议。 |

### 最近验证

- 已扫描 `gen-b/gen-b-client/src` 和 `gen-b/gen-b-client/index.html`。
- 已生成 `docs/requirements/CLIENT_I18N_COPY_MAP.md`。

### 下一步

如确认英文对照无问题，下一步可开始客户端 i18n 字典和语言切换开发。

---

## 当前任务：Runtime/CLI 生产底座继续增强

### 目标

在上一轮生产底座改造基础上，继续把可用骨架补成更接近生产可落地的能力。

### 成功标准

- 每个子任务都有明确实现范围。
- 每个已完成子任务有测试或验证记录。
- 任务结束后有报告沉淀。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 补齐项目文档骨架 | 已完成 | 文件存在检查 | 已新增 `ROADMAP.md`、`CHANGELOG.md`、`docs/INDEX.md` 等。 |
| 安全中间件扩展 | 已完成 | runtime pytest | 已支持 API Key、JWT hook、mTLS hook、安全上下文、请求大小限制、脱敏日志。 |
| 统一执行链路 | 已完成 | runtime pytest | `BaseEmployeeAgent` 默认走 `AgentRuntimeCore`。 |
| PostgreSQL asyncpg 连接池 | 已完成 | runtime pytest | `postgresql_storage_v2.py` 已改为懒加载 asyncpg pool。 |
| OpenTelemetry 可选接入 | 已完成 | runtime pytest | 已新增 no-op 安全接入。 |
| LLM retry/backoff/限流/usage | 已完成 | runtime pytest | Alaya adapter 已支持基础能力。 |
| CLI 模板同步 | 已完成 | cli pytest | 已同步安全、OTEL、LLM、policy、workflow 配置。 |
| Policy YAML/JSON DSL | 已完成 | runtime pytest | 已支持简单字段规则。 |
| Workflow checkpoint/resume 基础 | 已完成 | runtime pytest | 已新增 JSON checkpoint store 和 pending approval 状态。 |
| Memory tenant/user/agent 隔离基础 | 已完成 | runtime pytest | 已新增 `MemoryScope` 和 scoped key。 |
| Policy DSL 组合条件、版本、灰度、回放 | 未开始 | 新增测试 | 后续增强。 |
| Workflow 生产级持久化 store | 未开始 | 新增测试 | 后续接 PostgreSQL/Redis。 |
| Memory retention 自动执行、删除审计持久化、检索权限过滤 | 未开始 | 新增测试 | 后续增强。 |
| LLM circuit breaker 完整熔断 | 未开始 | 新增测试 | 后续增强。 |
| JWT/mTLS 真实业务校验实现 | 未开始 | 集成测试 | 需要确认业务认证源或网关约定。 |

### 最近验证

- `bank-agent-runtime`：`python -m pytest`，46 passed。
- `bank-agent-cli`：`python -m pytest`，4 passed。

### 下一步

优先建议做：

1. Policy DSL 组合条件、版本、灰度和回放。
2. Workflow checkpoint store 从 JSON 抽象到可替换接口，并补 PostgreSQL/Redis 实现。
3. Memory 删除审计持久化和检索权限过滤。

## 新任务模板

复制下面内容新增一个任务段：

```md
## 任务：一句话说明任务

### 1. 背景

为什么要做这个任务？
用户现在遇到了什么问题？
如果不做，会有什么影响？

### 2. 目标

这次最终要得到什么结果？

用普通话描述，不写技术细节。

### 3. 范围

本次要做：

- xxx
- xxx

本次不做：

- xxx
- xxx

### 4. 完成标准

满足下面这些条件，才算完成：

- [ ] 用户可以……
- [ ] 页面可以……
- [ ] 接口可以……
- [ ] 原有功能没有坏……
- [ ] 已完成测试……

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 理解现有代码和文档 | 未开始 | 写出影响范围 |
| 2 | 修改代码 | 未开始 | 查看 diff |
| 3 | 启动项目 | 未开始 | 前后端正常运行 |
| 4 | 测试接口 | 未开始 | 接口返回正确 |
| 5 | 测试页面 | 未开始 | 浏览器截图/操作通过 |
| 6 | 提交代码 | 未开始 | Git 有提交记录 |
| 7 | 写报告 | 未开始 | `records/reports/` 有记录 |

### 6. 当前进度

当前做到哪一步：

- 进行中：xxx
- 已完成：xxx
- 阻塞：xxx

### 7. 验收记录

实际测试了什么：

- [ ] 后端构建
- [ ] 前端构建
- [ ] 登录流程
- [ ] 主要页面
- [ ] 关键接口

测试结果：

写清楚通过/失败/失败原因。

### 8. 风险和遗留问题

还有什么没解决？
有没有需要你或同事确认的地方？
```

---

## 任务：将已验证测试分支合并到同事 create-genB

### 1. 背景

`codex/company-genb-sync` 已经完成联调验证，里面包含同事 `create-genB`、你的 `feature/genesis-client` 和管理端验证修复。现在需要把验证通过的代码合并回同事分支 `create-genB`。

### 2. 目标

让公司 GitLab 上的 `create-genB` 更新到已验证通过的测试分支状态。

### 3. 范围

本次要做：

- 拉取公司远端最新分支。
- 确认 `create-genB` 没有新的未合并提交。
- 将 `codex/company-genb-sync` 合并到 `create-genB`。
- 推送 `create-genB` 到公司 GitLab。
- 做基础分支状态确认。

本次不做：

- 不改业务代码。
- 不重新部署服务器。
- 不修改 `feature/genesis-client`。

### 4. 完成标准

满足下面这些条件，才算完成：

- [x] 已确认远端 `create-genB` 没有新提交。
- [x] `create-genB` 指向已验证测试分支最新提交。
- [x] 公司 GitLab `create-genB` 推送成功。
- [x] 本地 `gen-b` 工作区干净。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 拉取远端分支 | 已完成 | `git fetch company` |
| 2 | 检查分支关系 | 已完成 | `git log` 显示 `create-genB` 是测试分支祖先 |
| 3 | 合并到 `create-genB` | 已完成 | `git switch/create/reset/merge` |
| 4 | 推送 `create-genB` | 已完成 | `git push company create-genB` |
| 5 | 状态确认 | 已完成 | `git status`、`git ls-remote` |

### 6. 当前进度

当前做到哪一步：

- 进行中：无。
- 已完成：远端拉取、分支关系确认、快进合并、推送和远端状态确认。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] 分支状态
- [x] 远端提交

测试结果：

- 本地 `create-genB` 已快进到 `2f10ded`。
- 远端 `company/create-genB` 已从 `864c67c` 更新到 `2f10ded`。
- 远端 `company/codex/company-genb-sync` 同样指向 `2f10ded`。
- 远端 `company/feature/genesis-client` 指向 `74ce9c9`。
- 本地 `gen-b` 工作区干净。

### 8. 风险和遗留问题

本次是直接更新同事共享分支 `create-genB`。推送前已确认远端 `create-genB` 为 `864c67c`，没有新增提交；测试分支 `2f10ded` 基于该提交，已完成快进推送。未重新执行构建和页面测试，沿用上一轮 `codex/company-genb-sync` 的完整验证结果。

---

## 任务：重建测试分支并合并同事分支和个人分支

### 1. 背景

当前 GitLab 上已经有同事分支 `create-genB` 和你的个人分支 `feature/genesis-client`。旧的 `codex/company-genb-sync` 是之前临时形成的测试分支，里面包含旧版同事代码和额外验证修复，分支语义不够干净。

### 2. 目标

把 `codex/company-genb-sync` 清空重建为标准测试分支：只从同事最新 `create-genB` 合并你的 `feature/genesis-client`，然后完成构建和关键页面/接口验证。

### 3. 范围

本次要做：

- 拉取公司 GitLab 最新 `create-genB` 和 `feature/genesis-client`。
- 将 `codex/company-genb-sync` 重置为最新 `create-genB`。
- 合并 `feature/genesis-client`。
- 构建验证后端、客户端、管理端。
- 执行关键接口和页面验证。
- 推送更新后的 `codex/company-genb-sync`。

本次不做：

- 不修改同事 `create-genB`。
- 不修改你的 `feature/genesis-client`。
- 不部署服务器。

### 4. 完成标准

满足下面这些条件，才算完成：

- [ ] `codex/company-genb-sync` 基于最新 `create-genB`。
- [ ] `codex/company-genb-sync` 已包含 `feature/genesis-client`。
- [ ] 后端构建或测试通过。
- [ ] 客户端构建通过。
- [ ] 管理端构建通过。
- [ ] 关键登录、门户、客户端、管理端页面验证完成。
- [ ] 测试分支已推送到公司 GitLab。

### 5. 执行计划

| 顺序 | 要做的事 | 状态 | 怎么验证 |
|---|---|---|---|
| 1 | 拉取远端分支 | 已完成 | `git fetch company` |
| 2 | 重建测试分支 | 已完成 | `git log` 显示基于最新 `create-genB` |
| 3 | 合并个人分支 | 已完成 | `git merge feature/genesis-client` |
| 4 | 构建验证 | 已完成 | `mvn test` / `npm run build` |
| 5 | 接口和页面验证 | 已完成 | HTTP / 浏览器测试 |
| 6 | 推送测试分支 | 进行中 | `git push --force-with-lease` |
| 7 | 写报告 | 未开始 | `records/reports/` 有记录 |

### 6. 当前进度

当前做到哪一步：

- 进行中：推送测试分支。
- 已完成：测试分支已重建、已合并个人分支、构建和页面接口验证通过。
- 阻塞：无。

### 7. 验收记录

实际测试了什么：

- [x] 后端构建
- [x] 前端构建
- [x] 登录流程
- [x] 主要页面
- [x] 关键接口

测试结果：

- 后端 `mvn test` 通过。
- 客户端 `npm run build` 通过。
- 管理端 `npm run build` 通过。
- Genesis 门户登录并进入 Gen-B 通过。
- 客户端 test_user 登录和智能体市场通过。
- 管理端 Dashboard 和智能体中心通过。
- 页面验证发现旧测试修复不在两条源分支中，已将验证修复提交 `89641e1` 挑回新测试分支，生成新提交 `2f10ded`。

### 8. 风险和遗留问题

`codex/company-genb-sync` 会被重建并强制推送，这是用户明确要求的“清空测试分支”。该操作不影响 `create-genB` 和 `feature/genesis-client`。

---

## 当前任务：创建并推送个人功能分支

### 目标

在公司 GitLab `gen-b` 仓库中新增你的个人功能分支，基于同事最新 `create-genB`，放入你负责的 Genesis 统一门户、客户端和统一权限相关代码，便于后续与同事分支合并到测试分支联调。

### 成功标准

- 基于最新 `company/create-genB` 创建 `feature/genesis-client`。
- 将本地 Genesis/客户端功能提交放入该分支。
- 构建或关键验证通过。
- 推送到公司 GitLab。
- 不覆盖同事 `create-genB`。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 拉取最新 `create-genB` | 已完成 | `git fetch company create-genB` | 最新为 `864c67c feat:侧边栏优化`。 |
| 创建个人功能分支 | 已完成 | `git branch --show-current` | 分支名：`feature/genesis-client`。 |
| 放入 Genesis/客户端提交 | 已完成 | `git log` / 构建 | 已 cherry-pick 为 `74ce9c9 feat: add genesis portal sso`。 |
| 构建验证 | 已完成 | Maven / npm build | 后端 `mvn test`、客户端 `npm run build`、管理端 `npm run build` 均通过。 |
| 推送 GitLab | 已完成 | `git push company feature/genesis-client` | 已推送到公司 GitLab。 |

### 最近验证

- 已确认当前测试分支 `codex/company-genb-sync` 干净。
- 已确认公司 `create-genB` 有新提交 `864c67c feat:侧边栏优化`。

### 下一步

个人功能分支已完成。后续可用 `feature/genesis-client` + `create-genB` 合并到测试分支联调。

---

## 当前任务：Gen-O SSO Ticket 接入文档

### 目标

为已有登录体系的 Gen-O 平台编写完整 SSO Ticket 接入文档，说明 Genesis 登录后如何免二次登录进入 Gen-O，同时保留 Gen-O 原登录。

### 成功标准

- 文档说明 Gen-O 有登录系统时的推荐接入方式。
- 覆盖 Genesis 侧接口、Gen-O 侧回调接口、ticket 校验、用户映射、登录态建立。
- 覆盖错误处理、安全要求、联调步骤、验收标准和需要 Gen-O 提供的信息。
- 更新项目文档索引。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 新增 Gen-O SSO 接入文档 | 已完成 | 文件检查 | 已新增 Gen-O 专项 SSO Ticket 文档。 |
| 更新索引 | 已完成 | `docs/INDEX.md`、`PROJECT_INDEX.md` | 已加入文档索引。 |

### 最近验证

- 已确认现有 `GENESIS_GENC_GENO_INTEGRATION_GUIDE.md` 是通用接入说明，需要补一份 Gen-O 专项落地文档。
- 已新增 `docs/integration/GENESIS_GENO_SSO_TICKET_INTEGRATION.md`。
- 已更新 `docs/INDEX.md` 和 `PROJECT_INDEX.md`。

### 下一步

可直接把 `docs/integration/GENESIS_GENO_SSO_TICKET_INTEGRATION.md` 发给 Gen-O 团队评审。

---

## 当前任务：Genesis 门户 SSO Token Exchange 修正与部署

### 目标

修正 Genesis 门户登录后的跨系统免登录链路：门户登录只产生 Genesis token；进入 Gen-B 时通过后端根据用户映射和授权换取 Gen-B token，不再在前端直接复用 Genesis token。修正后完成本地验证并部署前后端服务器。

### 成功标准

- Genesis 登录接口仍使用 `genesis_users`。
- 前端不再在登录成功时把 Genesis token 写入 `genb-client-token`。
- 点击 Gen-B 时调用后端 exchange 接口，根据 `GEN_B` 映射和授权换取 Gen-B token。
- 换取成功后写入 `genb-client-token` 并进入 `/my-agents`，不需要再次登录。
- 未映射、未授权、平台未解锁时不能换取 Gen-B token。
- 后端测试或编译通过，前端构建通过。
- 部署前端和后端，并验证线上门户登录到 Gen-B 不二次登录。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 新增后端 Gen-B token exchange | 已完成 | 后端测试/接口验证 | 已新增 `/api/v1/genesis/sso/gen-b/token`。 |
| 修改前端进入 Gen-B 的 token 换取逻辑 | 已完成 | 前端构建/浏览器验证 | 登录时不再写 Gen-B token，点击 Gen-B 时 exchange。 |
| 更新接入文档 | 已完成 | 文档检查 | 已删除“复用 Genesis token”的错误说明。 |
| 本地构建和联调 | 已完成 | `mvn test`、`npm run build`、浏览器 | 已验证门户登录后 exchange 进入 Gen-B，不二次登录。 |
| 部署服务器 | 已完成 | 线上 URL 验证 | 前端和后端均已部署。 |
| 记录部署报告 | 已完成 | records | 已新增部署记录。 |

### 最近验证

- 已确认当前 `GenesisPortalService.login()` 查 `genesis_users`。
- 已确认前端当前存在不严谨逻辑：登录成功后直接写 `genb-client-token`。
- 已新增后端 Gen-B token exchange：`POST /api/v1/genesis/sso/gen-b/token`。
- 前端已改为点击 Gen-B 时调用 exchange，成功后才写入 `genb-client-token`。
- 后端 `mvn test` 通过。
- 前端 `npm run build` 通过，存在既有 chunk 体积 warning。
- 本地浏览器验证：清空旧 token 后登录 Genesis，点击 Gen-B 进入 `/my-agents`。
- 本地浏览器验证：`genesis-portal-token` 和 `genb-client-token` 均存在且内容不同。
- 已部署前端到 `/ayala/genb-client/`。
- 已部署后端 jar 到 `/app/gen-b-console/gen-b-console-1.0.0.jar`。
- 线上接口验证：`/genb-client/api/v1/genesis/auth/login` 和 `/genb-client/api/v1/genesis/sso/gen-b/token` 均返回成功，两个 token 不同。
- 线上浏览器验证：从 `/genb-client/portal/login` 登录后点击 Gen-B，进入 `/genb-client/my-agents`，不二次登录。

### 下一步

如后续接 Gen-C/Gen-O，按文档补用户映射和 ticket/token exchange。

---

## 当前任务：Genesis 统一门户参考图融合重写

### 目标

以 HTML 原型的布局、登录框交互和解锁节奏为功能基准，以参考 PNG 的蓝色粒子波纹视觉为背景基准，重写 `/portal/login` 门户页视觉。

### 成功标准

- 参考 HTML 和参考 PNG 已放到项目可访问目录，浏览器可直接打开对照。
- 门户页主内容上下左右居中，不再整体偏上。
- 登录输入框聚焦、输入、浏览器 autofill 时不出现白底。
- 背景是动态粒子波纹效果，视觉接近参考图，不是静态纯色。
- 登录后平台通道按顺序点亮，Gen-B 可访问，Gen-C/Gen-O 锁定提示。
- `npm run build` 通过，并用浏览器截图/DOM 验证。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 放入参考 HTML 和参考 PNG | 已完成 | 文件存在检查 | 已放入 `gen-b-client/public/reference/`。 |
| 重写门户布局和视觉 | 已完成 | 浏览器截图对比 | 已重写布局、登录框、平台通道和 Canvas 背景。 |
| 构建验证 | 已完成 | `npm run build` | 构建通过，存在既有大包 warning。 |
| 浏览器登录和截图验收 | 已完成 | `/portal/login` 实测 | 已验证参考文件可访问、登录点亮、无白底、无首屏溢出。 |
| 更新报告 | 已完成 | `records/reports/` | 已新增 `20260709-REPORT-genesis-portal-reference-fusion.md`。 |

### 最近验证

- 已复制 `genesis-engine-sso.html` 到 `gen-b/gen-b-client/public/reference/genesis-engine-sso.html`。
- 已复制参考图到 `gen-b/gen-b-client/public/reference/genesis-portal-reference.png`。
- `npm run build` 通过，存在既有 Vite 大包 warning。
- 浏览器验证 `/portal/login`：首屏无纵向溢出，输入框背景为深色，登录后 Gen-B 解锁、Gen-C/Gen-O 锁定。
- 浏览器验证 `/reference/genesis-engine-sso.html` 和 `/reference/genesis-portal-reference.png` 可访问。

### 下一步

如仍需继续提质，下一步建议只针对背景密度、品牌 logo 细节和平台图标资产做二次视觉精修。

---

## 当前任务：Genesis 门户登录框比例修正与外部参考复核

### 目标

重新检查 `/portal/login` 实际页面，并结合成熟 SSO/企业登录页参考，修正登录框过小、左右视觉权重不均衡的问题。

### 成功标准

- 已打开当前页面并记录登录框实际尺寸。
- 已联网参考成熟 SSO/企业登录页品牌化做法。
- 登录卡片宽高、输入框高度、按钮高度明显放大，左侧认证区和右侧平台通道视觉权重接近。
- 登录前后输入框不出现白底。
- `npm run build` 通过，浏览器截图/DOM 验证通过。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 检查当前页面尺寸 | 已完成 | 浏览器 DOM 测量 | 当前登录卡 `410×277`，确实偏小。 |
| 联网查找成熟登录页参考 | 已完成 | Web 搜索 | 参考 Auth0、Okta、Microsoft Entra 的品牌化登录页思路。 |
| 放大登录卡并调整布局 | 已完成 | 浏览器截图/DOM 测量 | 登录卡、输入框和按钮已放大。 |
| 构建验证 | 已完成 | `npm run build` | 构建通过，存在既有大包 warning。 |
| 浏览器登录验收 | 已完成 | `/portal/login` 实测 | 登录前后均验证通过，已截图。 |
| 更新报告 | 已完成 | `records/reports/` | 已新增 `20260709-REPORT-genesis-portal-login-size-fix.md`。 |

### 最近验证

- 当前页面登录卡尺寸：`410×277`。
- 当前表单尺寸：`361×228`。
- 当前平台区尺寸：`520×378`。
- 修改后登录卡尺寸：`500×427`。
- 修改后表单尺寸：`431×274`。
- 修改后输入框尺寸：`431×58`。
- 登录后 Gen-B 解锁、Gen-C/Gen-O 锁定，首屏无滚动溢出。

### 下一步

放大登录卡和输入区域，使左侧认证区接近右侧平台区的视觉重量。

---

## 当前任务：Genesis 门户顶部文案去重

### 目标

按参考图保留顶部 `Genesis Engine` 主标题，删除 `Single Sign-On / 一次登录 / 通行 Genesis Engine` 与登录卡说明之间的重复表达。

### 成功标准

- 页面不再同时出现两套“统一登录/一次登录/解锁入口”说明。
- 顶部内容以参考图为准，展示中央 `Genesis Engine`。
- 登录卡只保留登录入口标题和必要说明。
- `npm run build` 通过。
- 浏览器确认无首屏溢出，并保存截图。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 删除重复宣传文案 | 已完成 | 代码检查 | 已删除 `Single Sign-On` 和“一次登录”文案区。 |
| 顶部改为参考图主标题 | 已完成 | 浏览器截图 | 已新增中央 `Genesis Engine`。 |
| 构建验证 | 已完成 | `npm run build` | 构建通过，存在既有大包 warning。 |
| 浏览器验收和截图 | 已完成 | DOM 测量/截图 | 无首屏溢出，截图已保存。 |

### 最近验证

- 页面文本不再出现 `Single Sign-On`、`一次登录`、`通行 Genesis Engine`。
- 顶部中央显示 `Genesis Engine`。
- `scrollHeight=720`，`clientHeight=720`，首屏无溢出。
- 截图：`records/reports/assets/20260709-genesis-portal-copy-simplified.png`。

### 下一步

后续如继续对齐参考图，优先补平台正式图标和优化背景细节。

---

## 当前任务：Genesis 门户 Logo 与 Gen-C/Gen-O 接入文档

### 目标

按最新要求调整门户顶部：左上角使用透明背景 Alaya.To logo，中央保留参考图中的 `Genesis Engine` 标题，不保留顶部横线，不展示 `Unified Access Portal`、`System Online` 等多余文案，并新增 Gen-C/Gen-O 接入说明文档。

### 成功标准

- 顶部中央保留参考图中的 `Genesis Engine` 标题。
- 顶部不再展示 `Unified Access Portal`、`System Online`。
- 左上角使用白底转透明后的 Alaya.To logo，大小参考客户端左上角。
- 页面不保留顶部横线。
- logo 位置不遮挡登录卡和平台卡，页面首屏不溢出。
- 新增 Gen-C/Gen-O 接入文档，说明第一阶段入口接入、用户映射、授权、未来 SSO ticket。
- `npm run build` 通过，浏览器截图验证。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 更新任务看板 | 已完成 | 检查 `CURRENT_TASKS.md` | 本段即为任务记录。 |
| 生成透明 logo | 已完成 | 文件存在检查 | 已生成 `alaya-to-logo-transparent.png`。 |
| 修改门户页顶部和 logo | 已完成 | 代码检查 | 左上 logo + 中央标题，已去掉横线。 |
| 新增 Gen-C/Gen-O 接入文档 | 已完成 | 文件检查 | 已新增并加入文档索引。 |
| 构建和浏览器验证 | 已完成 | `npm run build` + 截图 | 构建通过，浏览器 DOM 和截图验证通过。 |

### 最近验证

- 已从用户提供图片生成透明 PNG：`gen-b/gen-b-client/src/assets/alaya-to-logo-transparent.png`。
- 已新增 `docs/integration/GENESIS_GENC_GENO_INTEGRATION_GUIDE.md`。
- 已更新 `docs/INDEX.md` 和 `PROJECT_INDEX.md`。
- 门户页顶部已改为左上角 logo + 中央 `Genesis Engine`，未保留横线。
- `npm run build` 通过，存在既有 chunk 体积 warning。
- 浏览器验证：`Unified Access Portal=false`，`System Online=false`，logo 尺寸 `142×49`，标题居中，header/footer 无 border，首屏无溢出。
- 截图：`records/reports/assets/20260709-genesis-portal-logo-left-title-center.png`。

### 下一步

等待用户确认是否继续微调 logo 亮度、标题大小或背景密度。

---

## 当前任务：Genesis 与 GenC 统一用户、角色和菜单权限

### 目标

让 Genesis 统一权限管理成为 GenC 用户平台授权、平台角色和权限分配的唯一配置入口；GenC 根据可信权限结果控制菜单、路由和后端接口。

### 成功标准

- Genesis 可以给 GenC 用户配置 `ADMIN` 或 `USER`。
- GenC 管理员拥有全部菜单，普通用户只拥有 AI 旅程首页和旅程编辑器。
- 普通用户不能通过地址或接口越权。
- GenB、GenC、GenO 的角色互不误用。
- 每一个实现步骤都有验证证据，未验证不标记完成。

### 步骤清单

| 步骤 | 状态 | 验证方式 | 备注 |
|---|---|---|---|
| 核对当前代码与数据库能力 | 已完成 | 代码和表结构定向检查 | 已确认当前只支持平台入口授权，不支持 GenC 内部角色权限。 |
| 编写详细设计 | 已完成 | 文档评审 | `docs/design/GENESIS_GENC_UNIFIED_AUTHORIZATION_DESIGN.md`。 |
| 编写逐步验证任务计划 | 已完成 | 文档评审 | `records/plans/20260720-PLAN-genesis-genc-unified-authorization.md`。 |
| 用户评审设计和范围 | 已完成 | 用户确认 | 用户已确认按 Subagent-Driven 方式逐项实施。 |
| 按计划实施和逐步验证 | 已完成 | 每一步的验证门禁 | Task 1 至 Task 14 均已通过；独立复审发现的权限问题已修复并再次复审通过。 |
| 写实现报告 | 已完成 | `records/reports/` | 八段式报告已完成；GenB `62ef762`、GenC `e6c19b8` 已本地提交，未推送。 |

### 最近验证

- GenC `main` 已拉取到当前远端最新提交 `c855780`。
- Genesis 已有用户、平台授权、角色继承授权、平台映射和 SSO ticket 表。
- 当前缺少平台专属角色、平台权限、角色权限和用户平台角色关系。
- ticket verify 当前不返回角色和权限。
- GenC 当前用户表、`/api/auth/me` 和 Vue Router 当前都没有角色权限信息。
- 现有 Genesis 权限管理页可以扩展为唯一配置入口。
- Task 1 已生成 PostgreSQL 与 SQLite 可恢复备份，主代理已复算 SHA256，并复核 `pg_restore --list` 与 SQLite `integrity_check`。
- 基线记录：`records/baselines/20260720-genesis-genc-unified-authorization-baseline.md`。
- Task 2 已完成第一个 TDD 纵向切片：授权快照测试先 RED 后 GREEN，GenC 认证测试 8/8 和编译通过。
- Task 3 已新增四张通用平台权限表和 GEN_C 内置数据；H2 幂等测试和后端 `mvn -o clean test` 20/20 通过。
- Task 4 已完成统一授权解析模块；主审发现并修复跨平台错误权限关系泄漏，专项测试 14/14、后端 `mvn -o clean test` 34/34 通过。
- Task 5 已扩展统一权限管理后端：读取和保存 `platformRoleCodes`、返回 resolver 计算的 `permissionCodes`，支持幂等替换、旧前端兼容和平台隔离；主代理单独执行 `mvn -o clean test` 43/43 通过。
- Task 6 已完成 Genesis 管理端 GenC 角色单选、角色继承提示和最终权限只读展示；表单契约测试 7/7、`npm run build` 通过，中英文 key 已核对。
- Task 7 已修复 GenC 角色继承授权用户缺映射的问题；缺失映射安全补建，人工停用不复活，过期授权和其他平台不触发；主代理执行后端 `mvn -o clean test` 50/50 通过。
- Task 8 已扩展 GenC ticket 校验响应，在消费瞬间通过统一 resolver 重算角色权限；平台停用、撤权、缺角色/权限均失败且不消费，GEN_O 保持兼容；主代理执行后端 `mvn -o clean test` 61/61 通过。
- Task 9 已完成 GenC 可信快照接收和严格认证边界；伪造、缺失、未知/多角色和畸形字段均失败关闭，SQLite 双迁移保留旧用户与画布；主代理执行 GenC 后端测试 20/20 和 compileall 通过。
- Task 10 已新增 GenC 服务端集中权限守卫和只读用户状态接口；已登记 API 按 permission 检查，未登记 API 默认 403，主代理执行完整测试 31/31 和 compileall 通过。
- Task 11 已建立 GenC 唯一导航注册表和异步路由守卫；三个页面共享菜单，USER 两项、ADMIN 三项，401/403 分流，主代理执行 Node 测试 10/10 和生产构建通过。
- Task 12 已完成真实 ADMIN/USER 浏览器端到端：门户、ticket、可信快照、3/2 菜单、ProcessOn 403、API 权限、ticket 重放及401/403均通过；截图和 evidence 位于 D 盘测试结果目录。
- Task 13 已完成全量回归：GenB后端61/61、客户端19/19、管理端7/7、GenC后端31/31、前端10/10；Genesis→GenB/GenO无二次登录，四类数据隔离与CORS通过。
- Task 14 已完成独立审查和两轮复审：修复存量角色回填、继承授权映射、禁用账号旧凭证、过期授权续开、无角色签票等问题；最终 GenB 后端 73/73 通过，未发现新的 P0/P1/P2。
- Task 15 已完成报告和本地提交：GenB `62ef762`、GenC `e6c19b8`；均位于 `codex/genesis-genc-authorization-20260720`，未推送；`.vite` 与 GenC `.env` 未进入提交。

### 下一步

后续如需上线，单独安排服务器数据库备份、迁移、配置、服务重启和线上回归；当前本地 8581 因旧 JAR 文件锁及环境变量保护未重载审查后的新 JAR。
# 当前任务：部署 GenB 英文客户端

## 背景

在管理端中文 `/genb/`、英文 `/genb-en/` 双版本基础上，用户要求同时部署客户端英文版本。客户端继续维护一套 Vue 源码，构建时生成独立英文产物，后端保持不变。

## 目标

- 英文客户端使用 `/genb-client-en/`，部署到 `/ayala/genb-client-en/`。
- 英文客户端 API 通过 `/genb-client-en/api/` 复用现有 GenB 后端。
- 中文 `/portal/login`、`/genb-client/`、管理端和其他系统不受影响。
- 发布前备份 Nginx 配置，构建、配置检查、加载和 HTTP 验证均通过。

## 计划

- [x] 核对客户端 Vite 配置、现网目录和 Nginx 配置。
- [x] 修正英文客户端构建 base 和语言缓存隔离。
- [x] 执行客户端测试与英文生产构建。
- [x] 备份服务器配置并部署英文产物。
- [x] 检查 Nginx、加载配置并验证页面、静态资源与 API。
- [x] 写入部署记录并更新索引。

## 结果

已将英文客户端发布到 `http://16.162.33.130/genb-client-en/`。入口、深层路由、主 JS 和共享 API 均验证成功；中文 `/genb-client/`、统一门户 `/portal/login`、中文管理端 `/genb/` 和英文管理端 `/genb-en/` 均保持 200。Nginx 备份为 `/etc/nginx/conf.d/alaya-to.conf.bak.20260722_173210`，完整过程见 `records/deployments/20260722-DEPLOY-genb-english-client.md`。

---
# 当前任务：固定中英文客户端语言并增加管理端入口

## 背景

中英文客户端已经分别部署，用户要求移除所有运行时语言切换按钮；同时，具备管理端权限的当前用户应能从客户端直接进入对应语言的管理端。

## 目标

- 中文客户端固定中文，英文客户端固定英文，不展示语言切换按钮。
- 以后端 `accessScopes` 中的 `ADMIN` 作为管理端权限主判据，并兼容旧响应角色。
- 中文客户端管理端按钮进入 `/genb/`，英文客户端进入 `/genb-en/`。
- 普通客户端用户不显示管理端入口。
- 测试、双语构建、双目录备份部署及线上验证通过。

## 组件边界

- `stores/auth.ts`：管理当前用户，并暴露唯一的管理端权限计算结果。
- `utils/consoleAccess.ts`：纯函数判断权限和解析中英文管理端 URL。
- `ClientShell.vue`：只负责按权限渲染入口并导航。
- `LoginView.vue`：复用统一权限判断处理“登录进入管理端”。
- `i18n/index.ts`：只使用构建期固定语言。

## 计划

- [x] 核对客户端权限数据、语言切换入口和管理端路由。
- [x] 实现固定语言和统一管理端权限判断。
- [x] 增加权限/URL 单元测试并执行完整测试。
- [x] 构建中英文产物并核对 base、文案和按钮代码。
- [x] 备份并部署中文、英文客户端。
- [x] 验证两套页面、静态资源、API 和现有管理端。
- [x] 写入部署记录并更新索引。

## 结果

中英文客户端均已重新部署。源码和线上页面不再存在语言切换按钮；管理员在中文客户端看到“进入管理端”并进入 `/genb/dashboard`，在英文客户端看到 “Admin Console” 并进入 `/genb-en/dashboard`；普通测试用户两边都不显示入口。Vitest 8 个文件 23 项、两项生产构建和四组真实浏览器权限场景全部通过。完整记录见 `records/deployments/20260722-DEPLOY-genb-client-fixed-language-console-entry.md`。

---
# 当前任务：提交并部署 GenC 角色菜单权限管理

## 背景

GenB 工作区已有未提交的 GenC 平台角色权限管理实现。用户要求收口、提交并部署，管理端需要分别发布中文 `/genb/` 与英文 `/genb-en/`，后端共享一套。

## 目标

- 管理员可在“统一门户权限”页面配置 GenC `ADMIN`、`USER` 的菜单/API 权限。
- 保存关系经过管理员、平台、角色和权限目录校验，并原子替换。
- GenB 重启不恢复管理员主动删除的角色权限。
- 中文、英文管理端包含同一功能并使用对应语言。
- 将上一项已部署的 Client 固定语言/管理端入口与本项权限功能拆成两个清晰提交并推送。
- 备份并部署 GenB 后端 JAR、中文管理端和英文管理端，完成接口与页面验收。

## 组件边界

- `GenesisPlatformRoleAdminService`：角色权限查询、校验与事务替换的唯一入口。
- `GenesisPlatformRoleAdminController`：HTTP 映射和 400/403 状态转换。
- `GenesisRolePermissionPanel.vue`：角色权限编辑 UI。
- `useGenesisRolePermissions.js`：加载、草稿、脏状态和保存副作用。
- `Index.vue`：只组合用户授权与角色权限两个页签。

## 计划

- [x] 审查当前 Git 改动、既有计划和功能边界。
- [x] 执行后端测试、前端单测和中英文构建。
- [x] 修正审查或测试发现的问题。
- [x] 分两次提交 Client 双语改动与 GenC 角色权限功能。
- [x] 推送 `create-genB`。
- [x] 备份并部署后端、中英文管理端。
- [x] 验证健康、管理员/非管理员接口及中英文页面。
- [x] 写入部署记录并更新索引。

## 结果

已创建并推送 `de78741`、`6975b81`。后端完整测试82项、前端角色权限测试3项和管理端中英文构建全部通过。生产后端已替换并恢复 `UP`；中文 `/genb/genesis-access`、英文 `/genb-en/genesis-access` 均显示2个角色和4个权限；管理员接口200、普通测试用户403。本次未修改生产角色权限组合。完整记录见 `records/deployments/20260722-DEPLOY-genc-role-permission-management.md`。

---
