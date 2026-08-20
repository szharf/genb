# 三个核心组件独立服务收敛任务计划

日期：2026-08-05
状态：执行中；M2已通过Gate C，M3已通过Gate D，M4已通过Gate E，进入M5的前置债务已完成，下一步执行M5总验收
范围：仅本地开发和本地验收，不操作服务器或服务器数据库

> 纠偏说明：本文件初版只写了目标、里程碑和Gate，没有完整使用
> `records/templates/PLAN_TEMPLATE.md`，不符合项目“每次开发前先形成标准任务计划”的规则。
> 2026-08-05已发生的Manifest、版本接口、短期消息裁剪和规划`CONVERSE`切片在本文件中
> 仅标记为“已有执行证据”，不倒填为开发前计划。自本次纠偏开始，后续开发必须按本计划逐项推进和更新状态。

## 背景

GenB将核心能力划分为五个系统和十四个核心组件。最新架构决定明确：

- 五个系统只承担GenB中的分类、展示和治理分组，不是五个共享运行服务。
- 十四个核心组件分别对应十四个公共组件服务。
- 各组件可由不同同事独立开发；负责人向GenB交付服务Interface、Manifest、OpenAPI、配置Schema和验收证据。
- GenB负责组件登记、配置发布、智能体绑定、凭证、Actor Token和治理，不接管组件业务数据库，也不默认代理每次业务调用。

本轮优先完善当前负责人承担的三项能力：

1. `SHORT_TERM_MEMORY`：短期对话上下文和跨会话任务工作台。
2. `PLANNING_REASONING`：需求澄清、Skill生成与校验，以及后续计划生命周期。
3. `LONG_TERM_MEMORY`中的Conversation Memory：对话记忆提取、跨会话召回、更正、反馈和遗忘。

长期记忆中的Knowledge Base由其他同事负责。它通过内部Adapter接入`long-term-memory-service`，不会作为第十五个核心组件，也不会要求智能体绑定两个长期记忆服务。

当前存在以下问题：

- `control-system-service`和独立服务目录存在短期记忆重复实现，公共真源不明确。
- 长期Conversation Memory仍主要位于`control-system-service`，尚未形成可独立运行的`long-term-memory-service`。
- 规划服务已经支持`ANALYZE/CONVERSE/GENERATE/VALIDATE/REVISE`，但GenB管理端此前没有完整暴露`CONVERSE`，计划生命周期也尚未完成。
- 旧设计文档默认“一个系统一个服务”，与十四组件分别交付的协作方式不一致。
- 当前工作树包含大量用户和同事的既有修改，不能通过重置、覆盖或大范围格式化整理工作区。

## 假设

- 十四个稳定`componentCode`继续使用当前GenB初始化Seed中的值，不在本轮重命名或迁移数据库枚举。
- `short-term-memory-service`作为`SHORT_TERM_MEMORY`最终唯一公共服务；现有独立服务的任务工作台模型保留，并按测试逐项吸收旧实现中的成熟能力。
- `planning-reasoning-service`继续作为`PLANNING_REASONING`唯一公共服务，不把Skill生成和计划生命周期拆成新的核心组件。
- 新建`long-term-memory-service`作为`LONG_TERM_MEMORY`唯一公共服务；Conversation Memory是内部模块，Knowledge Base以权限保持不变的Adapter接入。
- 在新服务完成专项、全量、真实依赖和18714验收前，旧公共入口只冻结新增功能，不提前删除。
- 当前统一登录识别修复和`riskLevel=UNKNOWN`的保守502处理属于必须保留的既有行为，不因本轮收敛而回退。
- 真实Redis和PostgreSQL验收只使用本地实例和本地测试数据；未配置本地凭据时测试应明确跳过，不能改用服务器数据库。
- 若代码现状与以上假设不一致，先更新本计划并说明影响，再继续开发，不静默扩大范围。

## 成功标准

- 十四个组件稳定码、五个系统分类、GenB代码Seed、Manifest Schema和设计文档完全一致。
- 三个当前组件分别具有唯一的公共服务定位、Manifest、OpenAPI、配置Schema、`/health/live`、`/health/ready`和`/version`。
- `SHORT_TERM_MEMORY`以`short-term-memory-service`为唯一公共真源，保留`taskId + sessionId`语义，并完成Redis原子写入、TTL、完整轮次裁剪、摘要、动态配置、脱敏、幂等和生产保护。
- `PLANNING_REASONING`在服务、GenB管理端和18714链路一致支持`ANALYZE/CONVERSE/GENERATE/VALIDATE/REVISE`；新增计划生命周期具备创建、步骤状态、观察、有限重规划、取消和终态合同。
- `LONG_TERM_MEMORY`对GenB只暴露一个组件服务；Conversation Memory支持提取、检索、去重、来源隔离、删除、更正/反馈和遗忘；Knowledge Base Adapter不可用时有明确降级且不伪造引用。
- GenB只登记一个当前可绑定的Implementation；不存在两个未声明的公共真源，也不存在对同一请求双写。
- 18714面向非技术用户的三个自然语言场景继续工作，不暴露Task ID、Session ID、JSON、组件操作码或内部凭证。
- 所有新增行为均先取得失败测试，再写最小实现转绿；专项测试、相关全量测试和合同一致性检查通过。
- 完成报告准确区分已验证、跳过和未完成内容；不把未运行的真实依赖测试标记为通过。

## 修改范围

### 计划修改

- `contracts/`：公共组件Manifest Schema和一致性测试。
- `short-term-memory-service/`：短期记忆唯一服务合同、配置、存储和测试。
- `planning-reasoning-service/`：规划与推理公开Interface和测试。
- `long-term-memory-service/`：长期Conversation Memory独立服务和Knowledge Base Adapter边界。
- `gen-b/gen-b-backend/`：Manifest接收、Implementation治理、测试Invoker和组件绑定所需的最小改动。
- `gen-b/gen-b-console/`：管理端组件测试入口及五项规划操作一致性。
- `control-system-test-agent/`及18714相关本地代码：只做三个自然语言场景的兼容接入和验收。
- `docs/`、`records/`、`CURRENT_TASKS.md`：架构、开发、接入、操作、计划和报告同步。

### 明确不修改

- 不实现其他同事负责的Knowledge Base、Tool Registry、Policy Guardrails等业务逻辑。
- 不新增第十五个核心组件，不把五个系统实现为新的共享业务服务。
- 不操作、连接、重启、部署或修改任何服务器及服务器数据库。
- 不删除9100/18714已完成的统一门户SSO修复，不恢复9100的`/core-agent/`旧入口。
- 不修改用户和同事的无关工作树内容，不执行`git reset --hard`、`git checkout --`等破坏性Git操作。
- 不在Gate通过前删除旧短期或长期入口，不保留完成切换后的长期双版本。

## 执行步骤

### M0：失败基线、架构决定和公共合同

状态：已完成；其中代码切片发生在计划模板纠偏之前，已记录流程偏差。

1. 读取项目索引、任务看板、记录索引、既有设计和当前代码。
2. 保存现有专项与全量测试结果，确认重复实现、公开路径和现有绑定。
3. 写架构ADR，明确“十四组件十四服务、五系统只分类”。
4. 写统一组件服务接入规范和机器可读Manifest Schema。
5. 先运行缺少Schema/Manifest的失败合同测试，再补充三项Manifest、OpenAPI和配置Schema。
6. 增加GenB Seed与Schema枚举一致性测试。

Gate A：只有稳定码、职责边界、Manifest和Seed完全一致，合同测试转绿后，才能进入组件业务迁移。
Gate A证据：`contracts/tests/test_component_manifests.py`当前为`2 passed`。

### M1：短期记忆唯一服务

状态：按用户指令暂缓，保留现有绿灯证据。

1. 逐项建立失败测试：任务工作台字段、跨Session恢复、完整轮次裁剪、动态配置、TTL、摘要、Redis并发、幂等、脱敏和依赖故障。
2. 保留`short-term-memory-service`现有`taskId + sessionId`模型，补入通过失败测试证明需要的成熟能力。
3. 增加并校验`/version`，使GenB可探测组件码、Implementation码、Interface版本和服务版本。
4. 让GenB Implementation、配置版本和18714绑定只指向独立服务。
5. 使用本地真实Redis验证原子写入、TTL、冲突和重试边界。
6. 连续执行两轮18714短期记忆自然语言场景。
7. 只有全部证据通过后，删除`control-system-service`中的旧短期公共入口和重复实现。

已有执行证据：`/version`和“按配置上限保留完整最近轮次、返回`trimmedMessageCount`”已经完成红绿测试。摘要、动态GenB配置、真实Redis、绑定切换和旧入口删除尚未完成。

Gate B：短期记忆专项、相关全量、真实Redis、GenB绑定和18714两轮场景全部通过后，才能删除旧入口并进入最终切换状态。

### M2：规划与推理完善

状态：已完成；2026-08-06通过Gate C。

1. 先以失败测试证明管理端操作集合缺少`CONVERSE`。
2. 使用同一个公开操作清单驱动前端下拉和请求校验。
3. 补齐GenB DTO校验和HTTP Invoker的`CONVERSE`路由，强制使用测试上下文中的`sessionId`。
4. 为计划生命周期依次定义失败HTTP测试：创建计划、读取计划、步骤开始/完成/失败、记录观察、有限重规划、取消和终态不可变。
5. 只实现让当前失败测试转绿的最小领域和存储逻辑。
6. 回归Skill生成、校验、修订、多轮澄清及`riskLevel=UNKNOWN`保守处理。
7. 验证管理端与18714自然语言生成Skill场景。

已有执行证据：

- `CONVERSE`已经贯通Vue测试台、GenB请求校验、HTTP Invoker和独立规划服务。
- 计划生命周期已完成进程内存纵向切片：创建/读取、步骤开始/完成/失败、观察追加、有限重规划、取消、身份隔离和终态不可变。
- 创建、步骤转换、观察、重规划和取消均要求并消费`Idempotency-Key`；相同请求重放首次结果，不重复产生状态变化。
- 运行时和静态OpenAPI均已发布六个计划生命周期Interface。
- 已新增`PlanStore` Interface、内存Adapter和PostgreSQL Adapter；计划聚合与幂等结果在同一事务写入，使用事务级锁保护同一计划和幂等键。
- `V003__planning_execution_plans.sql`已在本地`bank_agent_db`执行，创建`planning_execution_plans`和`planning_plan_idempotency`，没有物理外键；跨服务实例读取和跨实例创建幂等均已通过公开HTTP测试。
- 四个本地规划启动入口都显式设置`options='-c search_path=bank_agent_db'`，防止在`public`产生第二套表；18712最新运行态为`store=POSTGRESQL`、`planStore=POSTGRESQL`。
- GenB本地数据库只登记`planning-reasoning-service-v1 -> http://127.0.0.1:18712`，`core-component-demo-agent`绑定为`ENABLED/PRIMARY`。
- 当前规划服务内存回归`40 passed, 4 skipped`，本地PostgreSQL专项`4 passed`，18714自然语言编排相关`50 passed`，GenB后端相关`23 passed`，管理端操作模型`1 passed`；`riskLevel=UNKNOWN`专项`1 passed`。
- 2026-08-06真实Chrome新建独立对话，输入“我想生成一个银行对公授信材料检查Skill”；系统先返回3项动态澄清问题，收到PDF输入、固定材料清单、交叉核对、Markdown输出和人工审批边界后才生成`generated-skill-244a473a27` v1完整正文。
- 浏览器结果显示“验证完成”，三项体验进度全部打勾；Skill包含Purpose、Required Inputs、Workflow、Constraints、Human Approval、Failure Escalation、Completion Criteria和Exception Handling，页面未暴露Task ID、Session ID、JSON或凭证。

计划生命周期公开Interface与状态约束：

| Interface | 行为 |
|---|---|
| `POST /api/v1/planning-reasoning/plans` | 从目标和有序步骤创建活动计划，写操作要求幂等键。 |
| `GET /api/v1/planning-reasoning/plans/{planId}` | 按`tenant + user + agent`隔离读取计划。 |
| `POST /api/v1/planning-reasoning/plans/{planId}/steps/{stepId}:transition` | 按状态机开始、完成或标记失败。 |
| `POST /api/v1/planning-reasoning/plans/{planId}/observations` | 追加可审计观察，不覆盖历史。 |
| `POST /api/v1/planning-reasoning/plans/{planId}:replan` | 失败后在额度内保留已完成步骤并替换未完成步骤。 |
| `POST /api/v1/planning-reasoning/plans/{planId}:cancel` | 取消计划并终止所有未完成步骤。 |

- 计划状态：`ACTIVE`、`REPLAN_REQUIRED`、`COMPLETED`、`CANCELLED`。
- 步骤状态：`PENDING`、`IN_PROGRESS`、`COMPLETED`、`FAILED`、`CANCELLED`。
- 步骤必须按`order`开始；`PENDING -> IN_PROGRESS -> COMPLETED/FAILED`。
- 步骤失败后计划进入`REPLAN_REQUIRED`，只允许重规划或取消。
- 重规划次数不得超过创建时的`maxReplans`；额度耗尽返回稳定冲突错误。
- `COMPLETED`和`CANCELLED`是不可变终态，后续状态写入返回冲突。

Gate C：已通过。五项现有操作与计划生命周期的每个公开Interface均有测试，专项、相关全量、本地PostgreSQL、GenB绑定和18714真实Chrome自然语言场景均已转绿，规划组件可验收。

### M3：长期Conversation Memory独立服务

状态：已完成；2026-08-06通过Gate D。

1. 建立`long-term-memory-service`最小可运行入口，先测试健康、版本和身份门禁。
2. 以HTTP失败测试固定提取、任务查询、检索、去重、软删除和来源隔离合同。
3. 从旧实现逐个纵向迁移Conversation Memory领域、In-memory和PostgreSQL Adapter。
4. 为更正、反馈、遗忘分别建立失败测试，确认审计与召回语义后实现。
5. 定义Knowledge Base Adapter Protocol、Fake Adapter和错误模型，不实现同事的知识库业务。
6. 测试Knowledge Base超时、无权限、撤权和不可用时不泄漏、不伪造、不混入对话记忆。
7. 使用本地PostgreSQL验证持久化、软删除、来源筛选和租约行为。
8. 新服务通过后切换GenB绑定和18714长期记忆场景，再删除旧长期公共入口。

Gate D：跨会话召回、用户/智能体隔离、来源筛选、更正、反馈、删除、Adapter降级和本地PostgreSQL证据全部通过后，才能删除旧长期入口。

Gate D证据：

- 独立服务非数据库全量`31 passed, 1 skipped`；跳过项为显式未注入DSN的PostgreSQL测试。
- 注入本地`genb_local`后PostgreSQL专项`1 passed`，覆盖持久化重开、scope隔离、幂等、更正、反馈、软删除和租约。
- GenB本地`long-term-memory-service-v1 -> http://127.0.0.1:18702`为唯一启用长期Implementation，三个现有绑定全部切换，旧`control-long-term-memory-iteration13`为`DISABLED`。
- 正式本地Actor Token验收输出：`status=SUCCEEDED cross_session=true source=CONVERSATION soft_delete=true actor_token=true`。
- 真实Chrome在18714新建两个可见会话，第一会话保存“我长期偏好采用现金流覆盖充分且波动较低的对公授信方案”，第二会话准确召回完整内容并显示“跨会话长期记忆验证成功”。
- 旧Control System长期HTTP路由、Worker启动和长期PostgreSQL ready依赖已删除；运行态旧路径返回404。GenB `runLongTerm`只接受`LONG_TERM_MEMORY_V1`，旧适配器请求被明确拒绝。
- Control System回归`50 passed, 3 skipped`，测试智能体`63 passed`，GenB六个核心组件相关测试类通过。
- 真实18704模型仍存在`MODEL_STRUCTURED_OUTPUT_INVALID`，因此Gate D的模型边界使用本地确定性Runtime；该Runtime从当前输入动态生成候选、不再返回固定示例，生产禁止使用。真实模型合规性保留为后续依赖问题，不冒充已验收。

### M4：GenB统一接入

状态：已完成；2026-08-06通过Gate E。

1. 先写Manifest导入、稳定码校验、重复公共Implementation拒绝和OpenAPI关联的失败测试。
2. 实现Manifest接收、Implementation登记、配置草稿/发布和状态推进。
3. 验证组件会话、服务凭证、Actor Token、scope和configVersion一致性。
4. 为三个组件建立服务直测与智能体绑定测试，不让浏览器接触内部凭证。
5. 明确直接调用链路：智能体获得GenB治理授权后调用组件服务，GenB不作为常态业务代理。

Gate E：重复真源被拒绝、三组件绑定和凭证负向矩阵通过后，才能进入总验收。

Gate E证据：

- 新增`POST /v1/core-components/manifests:import`，校验固定系统/组件code、健康路径角色、HTTP(S)根地址、OpenAPI版本、配置Schema、`BEARER_JWT`、`component:` scope和隔离维度；导入后关联PUBLISHED接口契约、Manifest与配置Schema。
- 既有Implementation仅在Implementation code、runtime、Interface版本、base URL、ready URL和调用Adapter一致时允许由Manifest接管；Manifest中的owner作为新治理元数据更新。另一个`REGISTERED`公共Implementation存在时返回409，同一Manifest重复导入也返回409。
- 导入Schema已进入配置草稿控制面，覆盖类型、必填字段、枚举、数值上下界、字符串/数组长度、嵌套items和`additionalProperties=false`；非法配置在创建草稿前返回400，合法配置可完成DRAFT到PUBLISHED。
- 服务凭证scope不再被组件绑定放大。组件会话和Actor Token只携带“绑定允许scope ∩ 凭证scope”；交集为空返回403。Java专项`16 tests`通过，其中Manifest导入4项、组件访问12项；额外覆盖“同Interface版本但OpenAPI checksum不同”必须返回409。
- 三服务身份专项通过：短期`2 passed`、规划`1 passed`、长期`3 passed`；Manifest/OpenAPI静态合同`2 passed`。静态OpenAPI现要求所有业务与健康操作均提供唯一用途的`operationId`，并与Manifest Interface版本一致。
- 隔离的本地GenB 18581连接本地PostgreSQL验收：长期Manifest成功接管现有Implementation并关联PUBLISHED契约；长期非法配置被Schema以400拒绝。短期Manifest面对三个现有`REGISTERED`实现返回409，证明重复真源门禁有效。规划现有1.0.0 PUBLISHED契约只含旧操作集合，与当前包含CONVERSE和计划生命周期的静态OpenAPI checksum不同，最终实现按409拒绝关联；试验早期在补checksum门禁前产生的规划Manifest关联和owner改动已经精确回退。
- 使用临时服务凭证取得三组件会话，返回`SHORT_TERM_MEMORY -> 18705/configVersion 6`、`PLANNING_REASONING -> 18712/configVersion 7`、`LONG_TERM_MEMORY -> 18702/configVersion 10`及各自最小scope；仅带规划scope请求长期记忆返回403。临时凭证验收后已撤销，隔离的18581/6381进程已停止。
- 本地短期三个启用Implementation仍分别承载现有智能体绑定。由于M1按用户指令暂缓，本轮不擅自停用或迁移这些绑定；因此短期Manifest关联留作M1迁移项，但当前GenB三组件绑定与直连授权链路已通过Gate E。
- 规划组件必须发布与当前完整OpenAPI匹配的新Interface版本并迁移Implementation/绑定，不能覆盖既有1.0.0 PUBLISHED契约。该项与短期旧绑定迁移共同作为M5总验收前置债务；Gate E只确认控制面拒绝错误真源/错误契约以及三组件授权直连矩阵，不把拒绝结果冒充接入成功。

### M5：总验收、删除旧入口和记录

状态：已完成（2026-08-06，Gate F通过）。

进入M5前置债务处理（2026-08-06已完成）：

1. 规划当前完整OpenAPI先升为Interface `1.1.0`；一致性Gate随后发现静态契约遗漏按Skill版本读取路由，按照已发布契约不可覆盖原则再升为补丁版本`1.1.1`。Manifest仅允许同一Implementation向更高语义版本原子升级，配置和绑定保持不变。
2. 新增通用Implementation原子收敛Interface；先以公开HTTP测试证明旧绑定无法一次性安全迁移，再实现“校验全部启用真源→迁移绑定→稳定code重命名→停用旧实现”的单事务行为。
3. 在本地PostgreSQL执行规划升版和短期收敛，验证最终每个组件只有一个`REGISTERED`公共Implementation，所有原启用绑定仍为`ENABLED/PRIMARY`并指向正确已发布配置。
4. 重启本地18705/18712后核对`/version`、运行时OpenAPI、Manifest和GenB契约一致；运行三组件会话及18714相关回归。任何步骤失败则事务回滚，不进入M5。

完成证据：

- 新增公开原子收敛Interface及写锁；遗漏旧真源返回409且不产生部分迁移，完整请求一次迁移3个旧绑定并停用2个旧实现。
- 本地PostgreSQL最终仅保留三个对应组件各自唯一的`REGISTERED`真源；短期5个现有启用绑定全部指向实现ID 4和PUBLISHED配置ID 6。
- 短期最终Interface为`1.1.0`，规划最终Interface为`1.1.1`；18705/18712的`/version`、运行时OpenAPI、静态OpenAPI和Manifest版本一致，运行时/静态路由集合分别为6/6和15/15。
- 8581真实三组件会话返回短期18705/config 6、长期18702/config 10、规划18712/config 7；验收临时凭据已撤销。18714健康为UP，测试智能体全量63项通过。
- 自动化：GenB相关Java 35项、规划40项（另4项环境跳过）、短期11项（另1项环境跳过）、Manifest合同2项通过。详细记录见`records/reports/20260806-REPORT-pre-m5-core-component-convergence.md`。

1. 运行三个组件专项测试、GenB相关全量、18714测试和静态合同检查。
2. 使用本地浏览器分别完成短期、长期、规划自然语言场景，保存可复核证据。
3. 检查OpenAPI、Manifest、运行时路由和文档一致性。
4. 检查日志、错误响应、前端和Git差异中没有凭证或敏感信息。
5. 确认新入口完整验收后删除旧公共入口，不保留双版本。
6. 更新`CURRENT_TASKS.md`、记录索引、设计/开发/操作文档并新增完成报告。

Gate F：只有所有必须项通过、跳过项有原因、旧入口已删除且文档与代码一致，任务才能标记完成。

M5完成证据（2026-08-06）：

- GenB后端154项通过（1项真实Redis并发用例因测试环境变量未注入而跳过），客户端41项通过并完成生产构建；SSO专项、一次性授权码、Redis会话和HttpOnly Cookie合同均通过。
- 短期11项、长期31项、规划40项、18714测试智能体64项、Control System 50项、Runtime 45项、Manifest合同2项通过；环境跳过项分别记录了Redis密码或PostgreSQL DSN缺失原因，前置M4已用本地真实Redis/PostgreSQL完成对应运行态验收。
- Headless Chrome完成统一门户授权回跳、HttpOnly Cookie检查、短期两轮召回、长期新建可见对话后跨会话召回，以及Skill先澄清后生成；生成结果2750字，浏览器控制台零错误。
- 三个Manifest与静态/运行时OpenAPI路由集合一致：短期6/6、长期9/9、规划15/15；Interface版本分别为1.1.0、1.0.0、1.1.1。
- `http://localhost:18714/`为唯一客户入口；`http://localhost:9100/core-agent/`仅返回`410 Gone`墓碑，Vite不再代理旧入口，不存在双版本。
- `git diff --check`通过，未发现凭证、授权码或Session Grant日志泄露；完成报告见`records/reports/20260806-REPORT-three-core-component-service-convergence-m5.md`。

## 验证方式

### 合同与静态一致性

- `contracts/tests/test_component_manifests.py`校验Manifest必填字段、稳定码、健康路径、OpenAPI和配置Schema。
- 比较Manifest Schema中的五个系统/十四组件枚举与`CoreComponentCatalogInitializer` Seed。
- 对比静态OpenAPI与运行时`/openapi.json`公开路径和operationId。
- 搜索重复`componentCode`公共Implementation、旧路径和文档中的过期系统级服务描述。

### 短期记忆

- Python HTTP专项和全量测试。
- 本地真实Redis集成测试：并发、幂等、TTL、原子裁剪、故障和恢复。
- 不同tenant/user/agent/task的隔离负向测试。
- 18714两个可见会话中的任务工作台恢复与短期上下文测试。

### 规划与推理

- Python五项操作与计划生命周期HTTP测试。
- GenB Java DTO、Service、Invoker和Controller测试。
- Vue公开模型测试以及生产构建。
- 18714多轮澄清、生成、校验和失败修订场景。
- `riskLevel=UNKNOWN`不得再次造成非预期502的回归测试。

### 长期记忆

- Conversation Memory提取、检索、去重、来源、软删除、更正、反馈和遗忘测试。
- Knowledge Base Fake Adapter权限、引用和不可用降级测试。
- 本地PostgreSQL集成测试。
- 18714同一用户新建明确可见的新对话后，召回旧对话稳定信息；不同用户不能召回。

### 总体验收

- 三组件Manifest、专项和相关全量测试全部通过。
- GenB管理端可登记、配置、绑定和测试三个独立服务。
- 18714保持HttpOnly Cookie统一登录，不暴露内部ID、JSON或凭证。
- 浏览器刷新、切换会话、新建对话和退出不回归。
- `git diff --check`只检查本轮实际修改文件；预先存在的无关问题单独报告，不擅自修复。

## 风险

- 当前工作树非常脏，部分目标文件已有用户或同事修改。每次编辑前后必须按文件核对，不能把整份脏文件误当成本轮交付，也不能为方便提交而覆盖原改动。
- 两套短期记忆的数据模型和隔离维度不同，直接复制旧目录可能破坏任务工作台和跨Session语义；必须按公开行为纵向迁移。
- 旧`control-system-service`同时承载短期和长期链路，提前删除任一入口都可能破坏18714；删除必须位于对应Gate之后。
- 动态配置、Actor Token和服务凭证同时参与运行时行为，若测试只覆盖开发Header模式，会形成虚假通过。
- 长期记忆Knowledge Base由其他同事交付，Adapter合同可能随对方Interface变化；变更必须通过版本和兼容测试处理，不能在聚合层猜测字段。
- 本地Redis/PostgreSQL未配置时，集成测试可能跳过；跳过不等于通过，也不能用服务器环境补证据。
- 前端依赖管理器可能自动重排`node_modules`；构建应使用既有锁文件和本地工具，任何下载均记录到`D:\default\Documents\install_download_log.md`。
- 计划模板纠偏发生在部分代码切片之后，流程已经出现一次偏差。后续任何范围变化、Gate变化或新增组件都必须先更新本文件和`CURRENT_TASKS.md`再开发。
