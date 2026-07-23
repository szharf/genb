# 核心组件平台详细实施计划

> 状态：执行中
> 日期：2026-07-23
> 总体设计：`docs/design/GENB_CORE_MEMORY_COMPONENTS_DETAILED_DESIGN.md`
> 开发总纲：`docs/development/CORE_COMPONENT_PLATFORM_DEVELOPMENT_GUIDE.md`
> 当前专项：`docs/development/RUNTIME_SYSTEM_INFERENCE_ENGINE_IMPLEMENTATION_GUIDE.md`

## 1. 项目结果

最终交付GenB管理控制面、五个系统服务、14个核心组件和标准智能体接入。所有组件通过统一注册、配置、绑定、身份、Interface、错误、测试、观测和发布规范接入；一期先完成Short-term Memory、Long-term Memory和Inference Engine Service。

## 2. 执行原则

- 采用纵向切片：每次从公共Interface进入，经过真实Module，返回可观察结果。
- 每个行为执行一次RED→GREEN，不批量编写脱离实现的测试。
- 外部Provider位于真实Seam；测试使用Fake Adapter，生产使用Direct Provider Adapter。
- GenB控制面不代理高频模型和记忆调用。
- Control System不直连模型Provider；智能体不直连存储或持有Provider密钥。
- 每个阶段必须具有可运行演示、自动化测试、文档和回滚说明。

## 3. 总体里程碑

| 里程碑 | 目标 | 主要产物 | 出口条件 |
|---|---|---|---|
| M0 契约和工程底座 | 固化code、Schema、错误、身份和CI | contract目录、服务骨架、lint/test | 契约评审和测试通过 |
| M1 最小Inference Engine | Fake路径覆盖五个Interface | runtime-system-service、OpenAPI、Fake Adapter | 本地可运行，接口测试通过 |
| M2 真实模型Provider | Chat/结构化/Embedding真实调用 | Direct Provider Adapter、秘密和合规配置 | 脱敏真实契约、费用和故障测试通过 |
| M3 GenB核心组件控制面 | 可注册、配置、绑定、授权三个一期组件 | DDL、Java Module、RBAC、管理Interface | 未绑定调用被拒绝，审计完整 |
| M4 Control短期记忆 | 会话窗口、摘要、TTL和隔离 | control-system-service、Redis Adapter | 连续/隔离/过期/降级E2E通过 |
| M5 Control长期记忆 | 提取、过滤、检索、过期和删除 | PostgreSQL、Worker、Runtime Inference Adapter | 跨会话/敏感拒绝/删除审计通过 |
| M6 管理端和测试智能体 | 三张真实卡、11张规划卡、独立测试台 | GenB Console、Agent A/B | 管理员和隔离演示通过 |
| M7 一期生产硬化 | 安全、容量、监控、灰度和回滚 | dashboard、runbook、部署制品 | 一期验收矩阵全部关闭 |
| M8—M12 其余系统 | 按Control→Perception→Interaction→Runtime完整化→Operations推进 | 11个组件Implementation | 每系统专项验收通过 |
| M13 完整RAG | Long-term Memory知识库实现 | 摄取、索引、检索、引用和治理 | RAG验收通过 |
| M14 全量验收 | 14组件和五系统业务闭环 | 两条银行E2E和证据包 | 总体验收通过 |

## 4. M0：契约和工程底座

### M0-WP1 稳定code

- 固化5个`systemCode`和14个`componentCode`。
- 建立语言无关的JSON/YAML目录。
- 为code唯一性、数量和禁止改名建立测试。

### M0-WP2 公共HTTP契约

- 定义成功`data/meta`信封。
- 定义RFC 9457 Problem Details扩展。
- 定义`requestId/traceparent/Idempotency-Key`。
- 定义cursor分页和RFC 3339 UTC。

### M0-WP3 身份契约

- 定义服务凭证、Actor Token、组件会话Claims和scope。
- 本地Static Identity Adapter只能显式启用。
- 默认生产配置必须拒绝未知身份。

### M0-WP4 工程质量

- Python项目使用`src`布局、类型标注、pytest和应用工厂。
- 测试通过公开HTTP Interface，不断言内部调用次数。
- 建立秘密扫描、格式、OpenAPI和依赖检查命令。

## 5. M1：最小Inference Engine

### M1-WP1 tracer bullet

行为：有权调用方提交普通Inference请求，经过Inference Module和Fake Provider，获得统一响应信封。

验收：

- 无身份返回401。
- 有`component:inference-engine:infer`时返回200。
- 响应包含content、modelAlias、usage、finishReason、requestId和componentCode。

### M1-WP2 结构化输出

- 接收受限JSON Schema。
- Fake Provider返回JSON文本。
- Inference Module解析并校验，返回`structured`。
- 非法JSON返回`MODEL_STRUCTURED_OUTPUT_INVALID`。
- 不尝试猜测修复业务数据。

### M1-WP3 Embedding

- 批量输入、维度、顺序和有限值校验。
- 空输入/超限/非法维度返回400。
- Provider空向量、NaN或维度不符返回502。

### M1-WP4 模型能力

- `GET /models`只返回调用方有scope的逻辑别名。
- 不返回secret、真实Endpoint或内部凭证。

### M1-WP5 健康

- live只检查进程。
- ready验证身份配置、路由和Provider状态。
- internal model health仅管理员/内部身份可用。
- Fake Provider在生产模式不能使服务ready。

### M1-WP6 流式

- SSE事件`started/delta/usage/completed/error`。
- sequence递增，断流只产生一次error。
- 客户端取消时终止上游生成器。

### M1-WP7 文档和运行

- `pyproject.toml`、README、`.env.example`和启动命令。
- OpenAPI文件与FastAPI导出契约一致。
- 不安装新依赖；当前使用已有可运行Python环境验证。

## 6. M2：真实Provider

### M2-WP1 Provider选型验证

- Chat/结构化Provider官方契约和脱敏调用。
- Embedding Provider官方契约、维度和批量限制。
- 费用、配额、地域、数据训练/保留/删除政策评审。

### M2-WP2 Direct Chat Adapter

- 鉴权、普通Chat、JSON Schema/JSON Mode、usage和finish reason。
- 400/401/403/429/5xx/超时归一。
- 日志秘密和Prompt脱敏。

### M2-WP3 Direct Embedding Adapter

- 批量、维度、顺序、数值和usage。
- 模型版本或维度变化必须生成新alias/index版本。

### M2-WP4 路由与可靠性

- 静态主路由和一个可选兼容Fallback。
- 限流、一次可控重试、熔断和健康移除。
- Alaya只作为独立可选Adapter，不阻塞M2。

## 7. M3：GenB控制面

### M3-WP1 数据迁移

- `core_systems/core_components`种子。
- Implementation、Interface、Endpoint、Config、Binding、Credential、Health、TestRun和Audit表。
- 唯一键、幂等迁移和回滚/向前修复说明。

### M3-WP2 Java Module

- Catalog、Implementation Registry、Interface Registry、Configuration、Binding、Credential和Component Session Module。
- Controller只做协议映射，权限在后端强制执行。

### M3-WP3 RBAC

- 菜单、路由、按钮和后端权限一致。
- 默认管理员写、授权用户最小只读/测试权限。
- 凭证明文只显示一次，数据库保存强哈希或公钥。

### M3-WP4 Runtime注册

- 注册`runtime-inference-default`Implementation。
- 发布Interface和配置Schema。
- 绑定Control System和Inference Test Agent。
- 未绑定、过期、吊销和scope不足测试。

## 8. M4/M5：Control System记忆

按`CONTROL_SYSTEM_MEMORY_IMPLEMENTATION_GUIDE.md`拆分：

- Identity/Policy骨架。
- Short-term Memory+Redis。
- Long-term Store+PostgreSQL。
- Extraction Job/Worker。
- Runtime Inference Adapter。
- 敏感过滤、幂等、TTL、保留和删除。
- Control契约、隔离、安全、性能和故障测试。

关键依赖：Runtime Inference Interface先于真实摘要和提取；Fake Runtime Adapter允许领域开发并行。

## 9. M6：GenB页面与测试智能体

- 14张固定卡，3张一期真实卡，11张规划卡。
- 三张真实卡的Implementation、Interface、配置、绑定、健康和测试页。
- Memory Test Agent A/B：同代码不同`agentId`。
- Inference Test Agent：普通、结构化、流式和Embedding。
- 浏览器E2E覆盖权限、禁用、错误和审计。

涉及Vue时必须按Vue Composition API、Router、Pinia和测试技能执行。

## 10. M7：一期上线门禁

- Provider和外部数据合规签字。
- SLO、容量、成本上限、限流和告警。
- PostgreSQL/Redis/Secrets/网关生产方案。
- 身份吊销、越权、注入、秘密零泄漏测试。
- 镜像、SBOM、OpenAPI、Schema、dashboard和runbook。
- 配置、路由、镜像、凭证和数据污染回滚演练。
- 总体设计第27章一期门禁逐项关闭。

## 11. 后续14组件计划

| 顺序 | 系统/组件 | 开发重点 |
|---|---|---|
| 1 | Control：Planner & Reasoner | 可审计计划、观察、重规划、取消，不暴露CoT |
| 2 | Control：Tool Registry | Schema、版本、scope、健康、授权发现 |
| 3 | Control：Policy Guardrails | ALLOW/DENY/REVIEW和不可绕过obligations |
| 4 | Perception：Data Connectors | 两类真实数据源、映射、脱敏、断路 |
| 5 | Perception：Context Encoder | 清洗、压缩、排序和token预算 |
| 6 | Interaction：Multimodal | 至少一种非文本输入/输出和恶意文件防护 |
| 7 | Interaction：Session Manager | 创建、恢复、跨渠道转接和并发冲突 |
| 8 | Runtime：Inference完整化 | 双模型、成本、缓存和生产级Fallback |
| 9 | Runtime：Action Executor | 幂等、审批、未知结果、补偿 |
| 10 | Operations：Observability | OpenTelemetry、业务回放和脱敏 |
| 11 | Operations：Security Filter | 输入/输出/工具参数检测和fail-closed |
| 12 | Operations：Feedback Loop | 反馈、数据集、评估、灰度和回退 |
| 13 | Long-term Memory完整RAG | 摄取、索引、权限、检索、重排、引用和删除 |

前三个一期组件包含在M1/M4/M5；上表是其余能力和Inference/Long-term的完整化。

## 12. 当前迭代（Iteration 1）

### 目标

完成M0最小公共约定和M1 Fake纵向切片，使`runtime-system-service`无需外部模型即可运行和测试。

### 范围

- 新建独立服务目录和Python工程。
- 实现应用工厂、身份Port、Inference Module、Fake Provider Adapter。
- 实现非流式、结构化、Embedding、models、live/ready和基础流式Interface。
- 完成公开Interface测试、OpenAPI、README和环境示例。

### 不包含

- Direct Provider真实调用。
- GenB数据库/Java/前端改动。
- Control System代码。
- 生产部署。

### Iteration 1完成标准

- [x] 单测/Interface测试全绿。
- [x] 未授权和无scope请求被拒绝。
- [x] JSON Schema和Embedding异常不会返回伪成功。
- [x] Fake Adapter可复现成功和故障。
- [x] OpenAPI、README、配置和测试命令完整。
- [x] 无Runtime SDK依赖、无秘密、无外部网络调用。
- [x] 报告、任务和索引更新。

## 13. 当前迭代（Iteration 2）

### 目标

在不改变调用方Inference Interface的前提下，实现离线可验证的OpenAI-compatible Direct Provider主链路和版本化路由配置，为真实Provider门禁联调提供基础。

### 范围

- `modelAlias`到Provider/model/capabilities/dimensions的静态发布路由。
- `env://` Secret Resolver；配置和测试中不保存API Key明文。
- 普通Chat、Provider原生JSON Schema、SSE和Embedding Adapter。
- Provider 429、4xx、5xx、连接、超时和非法响应统一错误。
- `/models`由发布路由动态生成；运行入口通过`MODEL_ROUTING_CONFIG`加载配置。
- 只使用外部HTTP Mock Transport验证，不访问真实Provider。

### Iteration 2完成标准

- [x] Direct Provider普通推理、结构化输出、流式和Embedding通过公开Interface测试。
- [x] 未发布别名、能力和Embedding维度fail-closed。
- [x] 重复别名、重复Provider、未知Provider、非HTTP地址和缺失Secret启动前失败。
- [x] 模型目录来自路由配置，不暴露Endpoint或secretRef。
- [x] 上游错误不回显Provider正文、密钥或Prompt。
- [x] 配置Schema、示例、README和阶段报告完整。
- [ ] 使用真实脱敏数据完成Provider官方契约、费用和数据政策门禁。

Iteration 2完成的是M2工程主链路，不代表M2整体完成；最后一项真实门禁通过后才能把M2状态改为完成。

## 14. 当前迭代（Iteration 3）

### 目标

在GenB后端建立核心组件控制面的第一条闭环，通过现有用户JWT和后端权限完成固定目录、Implementation注册、配置发布和智能体主绑定解析。

### 范围

- `core_systems/core_components`固定种子，页面和通用Interface不能新增第六个系统或第15个组件。
- Component Implementation注册及组件内唯一约束。
- 配置草稿、乐观锁字段和不可变发布动作；秘密只保存引用。
- 已发布配置的智能体主绑定及生效解析。
- `component.read/configure/bind`权限接入现有GenB角色权限链。
- H2真实登录、JWT、HTTP、Module和JPA纵向集成测试。

### Iteration 3完成标准

- [x] 固定五系统/14组件幂等种子和受保护目录Interface。
- [x] 管理员可注册固定组件的Implementation。
- [x] 配置可创建草稿并发布，发布后无修改入口。
- [x] 配置正文嵌入密码、API Key、token或secret字段会被拒绝。
- [x] 智能体只能绑定存在的Implementation和已发布配置。
- [x] 同一`agentId + componentCode`最多一个主绑定。
- [x] 匿名和普通用户不能访问核心组件控制面。
- [x] GenB后端89项测试全部通过。
- [ ] 显式数据库迁移、审计、凭证/组件会话、健康、测试运行和前端页面。

Iteration 3完成的是M3最小控制面闭环，不代表M3整体完成；最后一项将在后续Iteration继续拆分。

## 15. 当前迭代（Iteration 4）

### 目标

在Iteration 3最小控制面之上补齐可停用、可恢复、可回滚、可审计的治理闭环，为后续服务凭证和组件会话建立安全前置条件。

### 范围

- Implementation启用/停用，停用后既不能新增绑定，也不能继续解析为生效绑定。
- 智能体绑定停用/恢复，生效查询只返回启用且Implementation可用的绑定。
- 按Implementation和profile查询配置版本历史。
- 将历史已发布配置复制为新的不可变已发布版本，不原地修改历史。
- 记录Implementation、配置和绑定的成功管理变更；审计只包含actor、action、target和result元数据。
- 审计查询最多返回最近200条，不保存或返回配置正文、secretRef和密码。

### Iteration 4完成标准

- [x] Implementation启停状态机及绑定门禁通过公开HTTP测试。
- [x] 绑定停用后不再生效，恢复后重新生效。
- [x] 配置列表按版本倒序返回，回滚生成递增的新PUBLISHED版本。
- [x] 管理变更带当前GenB用户名写入审计。
- [x] 审计响应不包含配置值或secretRef。
- [x] `component.read/configure/bind`继续由后端方法权限强制执行。
- [x] GenB后端93项测试全部通过。
- [ ] 显式数据库迁移、凭证/组件会话、健康、测试运行和前端页面。

Iteration 4完成M3治理状态闭环；下一迭代进入服务凭证和短时组件会话，不连接远程库、不部署，直到迁移与秘密管理门禁准备完成。

## 16. 当前迭代（Iteration 5）

### 目标

为逻辑智能体建立机器身份，并由GenB根据机器身份、当前登录Actor、智能体使用权、组件绑定和scope签发短时组件会话；高频数据面调用不回调GenB。

### 范围

- 管理员签发、查询和立即吊销服务凭证。
- `gmb_live_<keyId>_<random>`使用32字节加密安全随机主体，只在签发响应展示一次。
- 数据库只保存bcrypt哈希、公开前缀、scope、状态、签发/过期/吊销/最近使用元数据。
- API Key经TLS头`X-Agent-Credential`交换5—15分钟组件会话。
- 组件会话只返回已请求、已绑定、已启用、配置已发布且scope允许的组件。
- Actor Token包含用途、jti、Actor、agent、session、credential key、有效scope和绑定快照。
- 组件会话使用与GenB登录Token隔离的派生签名密钥，并在登录过滤器再次检查token用途。
- 凭证签发/吊销和组件会话签发写入脱敏审计。

### Iteration 5完成标准

- [x] secret只在签发响应出现一次，列表和审计不返回secret或hash。
- [x] 凭证默认90天、可指定过期时间、最长365天，并支持立即吊销。
- [x] 篡改、过期和吊销凭证不能换取组件会话。
- [x] scope未知、scope不足和Actor无智能体使用权均被后端拒绝。
- [x] 组件会话返回稳定端点、Interface版本、配置版本和有效scope快照。
- [x] 组件Actor Token不能冒充GenB/Genesis登录Token。
- [x] GenB后端101项测试全部通过。
- [ ] 凭证轮换宽限期、非对称签名/JWKS、tenant映射、在线会话吊销、显式数据库迁移和前端页面。

Iteration 5完成M3机器身份和短时授权最小闭环，但不代表生产身份体系完成。正式数据面接入前必须补tenant来源、非对称签名/JWKS或工作负载身份，以及数据库迁移和密钥轮换演练。

## 17. 当前迭代（Iteration 9）

### 目标

进入M4，在新建的`control-system-service`中交付Short-term Memory首条真实HTTP纵向切片，让Control System开始拥有数据面实现，而不再只有GenB控制面记录。

### 范围

- RS256 Actor Token + 服务凭证双凭证Identity Module。
- `turns:commit`、`context:prepare`、session clear三个Interface。
- tenant/user/agent/session四维隔离、幂等、冲突、最近窗口预算和持久化前脱敏。
- In-memory/Redis两个SessionStore Adapter，Redis使用Lua原子提交、TTL和HMAC键。
- live/ready/version、OpenAPI、本地启动工厂和公开Interface/安全/集成测试。

### 完成标准

- [x] commit后同一作用域prepare可召回，四维任一变化均隔离。
- [x] 双凭证、RS256签名、过期、agent/component/scope一致性在后端强制。
- [x] 同幂等key同内容不重复写，不同内容返409。
- [x] Redis原子写、TTL、HMAC键、清理和故障错误通过真实集成测试。
- [x] 密码和Bearer Token在进入存储前脱敏，错误不泄露请求正文或连接信息。
- [x] 旧Runtime SDK零依赖，OpenAPI与FastAPI导出完全一致。
- [x] 16项自动测试和真实Redis验证通过，测试键残留为0。

### 未解决的下一阶段门禁

GenB Iteration 5当前签发的Component Session仍是派生对称密钥JWT，且claims尚无Control System设计需要的`tenantId/iss/aud/components`。Iteration 9因此只允许`local/test`使用本地凭证Adapter，`production`启动会fail-closed。下一Iteration必须先完成GenB非对称Actor Token/JWKS与服务凭证内省契约，才能做真实智能体联调。

Iteration 9不包含Long-term Memory、摘要、真实Runtime Inference、测试智能体和管理端测试台。

## 18. 当前迭代（Iteration 10）

### 目标

完成GenB与Control System之间的生产方向身份契约：RS256 Actor Token、JWKS和受保护服务凭证内省，并通过真实Adapter解除测试智能体联调前的身份门禁。

### 范围与门禁

- 兼容现有Component Session交换响应，Actor Token升级为带`kid`的RS256 JWT。
- claims包含受信`tenantId/userId/agentId/sessionId/components`以及固定`iss/aud`和标准时效字段。
- GenB发布仅含公钥的JWKS，Control System固定算法并按`kid`选键。
- 内省Interface使用独立内部凭证，不复用用户JWT或agent服务凭证作为调用方身份。
- Control System通过HTTP/JWKS Adapter接入，GenB不可用、未知键、无效凭证均fail-closed。
- scope统一为`component:<component-code>:<action>`；本轮不兼容两套scope命名。
- tenant一期为GenB服务端受信配置；多租户目录映射仍是后续门禁。
- 不部署、不修改远程数据库、不创建表或物理外键。

### 完成标准

- [ ] 独立使用JWKS可验证现有组件会话返回的Actor Token。
- [ ] 内省有效/无效/过期/吊销矩阵和内部调用认证通过。
- [ ] Control System真实Adapter身份链及fail-closed测试通过。
- [ ] GenB、Control System全量回归、安全扫描、报告和精确提交完成。

## 19. 提交策略

- 当前根工作区存在大量历史未跟踪文件和子仓库改动，只精确暂存本计划、当前相关文档和新服务文件。
- 不使用`git add .`，不提交日志、缓存、虚拟环境、构建产物或无关子仓库状态。
- 提交前列出暂存清单、运行`git diff --cached --check`并复核无秘密。
