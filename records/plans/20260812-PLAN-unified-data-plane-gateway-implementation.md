# GenB统一数据面网关详细方案与实现任务计划

- 日期：2026-08-12
- 状态：已完成（M0-M5与Gate A-F全部通过）
- 负责人：GenB平台开发
- 范围：只在本地完成架构决策、代码、迁移、测试、镜像和样例配置
- 依赖：无服务器前置依赖
方法：M0失败基线开始，测试先行，Gate A-F不可跳过

## 文档目的与模板依据

本文件既是实施计划，也是本轮开发前必须遵守的详细方案基线。开发中不能依赖聊天记录补齐关键决定；如果方案、接口、身份、数据或Gate发生变化，必须先更新本文件和对应ADR，再修改代码。

结构采用三类成熟模板的组合：

- [arc42官方模板](https://arc42.org/overview/)：上下文、解决策略、模块视图、运行时视图、横切概念、质量与风险。
- [Kubernetes KEP官方模板](https://github.com/kubernetes/enhancements/blob/master/keps/NNNN-kep-template/README.md)：目标/非目标、详细设计、测试计划、毕业条件、升级回滚、可观测性和生产就绪。
- [MADR官方模板](https://adr.github.io/madr/decisions/adr-template.html)：决策驱动、候选方案、选择结果、后果和确认方式。

外部模板只用于组织文档；以下项目事实和实现约束以当前GenB代码及本地运行态为准。

## 背景与问题

当前存在两条彼此不同的链路：

1. 18714测试智能体自行实现一次性授权码、Redis会话、HttpOnly Cookie和Component Session；其他旧智能体没有统一实现。
2. 当前三个核心组件由智能体取得GenB签发的Component Session后直连组件服务，组件必须理解GenB Actor Token、Scope和隔离合同。

这造成以下问题：

- 每个智能体若要识别门户用户，都要重复开发登录适配层。
- GenB“启动/停止智能体”和“识别当前访问用户”混为一谈；直接打开IP端口不能证明用户身份。
- 服务提供方通常只提供自己的服务地址、接口和调用方式，不会实现GenB权限体系。
- 智能体依赖具体服务地址、认证方式和请求格式，更换服务实现时需要重复修改多个智能体。
- 外部API Key可能扩散到智能体，权限、限流、审计和错误处理分散。
- 如果把所有业务流量塞进现有GenB Java后端，又会使控制面承受SSE、文件和高频组件调用压力。

## 当前事实与失败基线

- 18714已有可工作的Agent SSO，但登录代码位于智能体自身，不具备跨智能体复用性。
- GenB客户端只有`core-component-demo-agent`优先使用`accessUrl`，旧智能体仍主要按独立端口打开。
- `ComponentManifestImportService`的Adapter和Scope表只覆盖短期记忆、长期记忆、规划与推理三个组件。
- 现有ADR规定“智能体获得治理授权后直连组件”，与本计划的统一组件调用网关冲突，必须由新ADR显式替代相关部分。
- 当前三个服务已经验证Actor Token与四维隔离；这些安全能力在迁移期间必须保留，不能为了网关接入而降低。
- 核心组件模板和18714当前只在本地，生产服务器尚未部署这些实现。
- 当前工作树很脏；用户及同事已有修改必须逐文件保护，不允许重置或大范围覆盖。

M0必须先把以下行为写成失败测试：旧智能体裸端口无法识别用户、浏览器伪造身份Header、未知上游地址、未绑定能力、停用实现、过期缓存、撤权未失效、外部凭证泄漏，以及不同用户共享有状态数据。

## 决策驱动与硬约束

### 决策驱动

- 一次登录改造覆盖全部智能体入口，而不是每个智能体实现SSO。
- 同事自行部署、自由命名服务，只需提供接口及最低机器认证材料。
- GenB保持低频控制面，不代理对话正文、文件和每次业务调用。
- 高频数据面可独立限流、缓存和扩容。
- 外部服务凭证只进入网关，不进入浏览器或智能体。
- 在现有两台服务器上可先以低资源单实例上线，未来不重写即可拆分扩容。

### 硬约束

- 五个系统只是GenB分类；14个固定`componentCode`继续作为平台能力码，但不是服务方项目名称。
- 服务方名称、项目名称、URL和部署方式自由；`implementationCode`在GenB内唯一。
- 有状态服务必须支持平台隔离键、独立实例或明确判定不支持多用户；网关不能伪造数据隔离。
- 无状态旧智能体可零改造；需要用户身份的智能体最多读取统一身份Token，不重复实现登录。
- 本计划只本地开发，不连接或修改生产服务器、Nginx、Redis和数据库。

## 候选方案与决定

| 方案 | 结论 | 原因 |
|---|---|---|
| 保持智能体直连组件，每个智能体自己接SSO | 拒绝 | 登录、凭证、Adapter和审计在每个智能体重复 |
| 所有流量进入现有GenB后端 | 拒绝 | 控制面承担SSE、文件和高频流量，故障和扩容耦合 |
| 访问网关与组件网关各自独立部署 | 作为未来目标 | 职责清晰，但当前服务器和运维成本不适合立刻增加两个应用进程 |
| 一个轻量数据面应用，内部两个Module；Nginx承载智能体字节流 | 一期采用 | 登录和能力治理集中，应用资源较低，内部接口允许未来拆分 |

决定的正面后果：一次改造复用到所有智能体、服务方接入门槛降低、凭证集中、GenB减压、实现可替换。负面后果：增加一次组件网络跳转、数据面成为新故障点、需要维护Adapter和缓存一致性、部分有状态旧智能体仍需最小适配或独立实例。

M0必须新增ADR，明确替代`20260805-ADR-fourteen-component-services-five-system-classification.md`中“智能体常态直连组件”的结论；14组件独立交付和五系统分类原则继续有效。

## 目标架构

```mermaid
flowchart LR
    U["用户浏览器"] --> N["Nginx统一入口"]
    N --> P["Genesis/GenB页面"]
    N -->|"auth_request"] D["统一数据面应用"]
    N -->|"通过后流式代理"] A["独立智能体"]
    A -->|"标准能力调用"] D
    D --> E1["现有三个组件"]
    D --> E2["同事自行部署的服务"]
    D --> R["专用Redis"]
    D -. "配置快照/Actor Token/审计批次" .-> G["GenB控制面"]
```

关键点：智能体的HTML、SSE、WebSocket和文件字节由Nginx直接转发，数据面应用只处理鉴权子请求和组件调用。因此“统一访问网关”是Nginx与访问控制Module的组合，不由Python应用代理所有智能体长连接。

## 现状到目标变更矩阵

| 对象 | 当前 | 目标 | 解决问题 | 收益/代价 |
|---|---|---|---|---|
| GenB后端 | SSO、组件会话、固定三组件Manifest | 管理能力、实现、Adapter、路由、Secret引用、策略、配置版本和网关身份 | 管理对象与外部服务解耦 | 控制面更完整，但需迁移和新接口 |
| GenB客户端 | 多数智能体打开IP端口 | 统一生成`/agents/{agentId}/` | 入口不再暴露真实端口 | 需兼容迁移状态 |
| Nginx | 静态/简单反代 | `auth_request`鉴权、动态白名单上游、流式代理 | 避免应用网关承载全部字节 | 配置更复杂，需防SSRF |
| 数据面应用 | 不存在 | 访问控制Module＋组件调用Module | 集中身份、策略、Adapter、缓存 | 新增单实例故障点 |
| 智能体 | 自己登录或无登录；直连组件 | 不实现SSO；按需读取签名身份；统一调用能力接口 | 降低重复改造 | 有状态智能体仍需读取身份或独立实例 |
| 核心组件 | 理解GenB双Token | 当前三个保留兼容；外部服务可只理解自己的机器认证 | 不要求同事实现GenB权限 | Adapter由平台维护 |
| Redis | 18714独立会话或现有共享实例 | 数据面专用会话、缓存、失效和审计缓冲 | 集中会话和缓存 | 需要TTL、容量和恢复规则 |
| 审计 | 分散 | 数据面统一生成、批量提交GenB | 可追溯且GenB不接每次正文 | 需要异步缓冲和丢失告警 |

## 上下文与信任关系

| 参与方 | 可信身份来源 | 可以知道 | 禁止知道/相信 |
|---|---|---|---|
| 浏览器 | Genesis登录＋网关HttpOnly Cookie | 页面与自己的响应 | 服务凭证、Actor Token、真实上游地址；浏览器提交的身份Header不可信 |
| Nginx | 数据面鉴权子请求结果 | 已发布上游地址、短时身份Token | 用户传入的`X-GenB-*`必须全部删除 |
| 智能体 | 网关注入的签名身份Token | 当前用户匿名/内部ID、agent、session | 不持有外部API Key，不信任请求正文身份 |
| 数据面应用 | 网关机器凭证、Redis会话、GenB快照 | 用户、授权、绑定、路由、Secret引用 | 不信任浏览器身份、任意URL或未发布配置 |
| GenB | 门户用户、RBAC和发布数据 | 控制面元数据与审计 | 不接收高频业务正文 |
| 外部组件 | 网关注入的机器认证和隔离键 | 完成操作所需最少数据 | 默认不获得门户Token、网关Cookie和服务方无关身份 |

生产上游必须不能被浏览器绕过网关直接访问；本地阶段通过测试网络和伪造直连负向测试固定该要求，真正防火墙调整留给部署计划。

## 目标Module与代码结构

新增根目录`genb-data-plane-gateway/`，采用Python ASGI实现以复用现有FastAPI/httpx/Redis经验并控制内存。逻辑Module不等于多个进程：

| Module | Interface | 责任 | 不承担 |
|---|---|---|---|
| Access Decision | `authorize(agentId, sessionCookie, requestMeta)` | 会话、访问授权、上游解析、身份Token | 不转发智能体正文 |
| Gateway Session | `create/resolve/revoke` | Redis会话、TTL、退出和重放保护 | 不保存对话历史 |
| Identity Token | `issue/verify` | 签名短时用户/agent/session上下文，提供JWKS | 不复用门户JWT |
| Capability Invocation | `invoke(capability, operation, context, payload)` | 绑定检查、路由、Adapter、凭证、错误 | 不暴露上游细节 |
| Adapter Registry | `resolve(adapterCode, version)` | 编译期白名单Adapter选择 | 一期不支持动态上传执行代码 |
| Control Snapshot | `refresh/getLastKnownGood` | 读取GenB版本化快照、原子替换 | 不逐请求查询数据库 |
| Cache | L1和Redis Adapter | 权限、路由、Token缓存与失效 | 不允许无界Key |
| Secret Resolver | `resolve(secretRef)` | 从环境/挂载Secret取值 | GenB数据库不存秘密正文 |
| Audit Sink | `append/flush` | 脱敏事件写Redis Stream并批量提交 | 不记录对话和文件正文 |

每个远程依赖均提供生产HTTP/Redis Adapter和内存测试Adapter，测试通过同一外部Interface，不穿透内部实现。

## 关键运行时场景

### 场景A：用户进入智能体

1. 浏览器访问`/agents/{agentId}/...`。
2. Nginx删除浏览器提交的全部`X-GenB-*`，向数据面内部鉴权Interface发起子请求。
3. 无有效网关Cookie时，返回登录跳转；GenB确认门户登录、用户权限、智能体发布及RUNNING状态并签发一次性Code。
4. 数据面应用使用唯一的网关机器凭证交换Code，不要求每个智能体保存服务凭证。
5. 数据面在Redis保存随机会话，浏览器只得到`genb_gateway_session`：HttpOnly、SameSite=Lax、Path=/agents；生产Secure，本地HTTP允许Secure=false。
6. 鉴权成功后返回已发布的上游和60秒以内的身份Token；Nginx流式转发到智能体。

### 场景B：智能体调用核心能力

1. 智能体服务端携带自身机器身份和网关注入的短时身份Token，请求`/component-api/v1/capabilities/{capabilityCode}/operations/{operationId}:invoke`。
2. 数据面验证token的audience、tenant/user/agent/session、过期和重放约束。
3. 从缓存快照检查智能体绑定、实现状态、操作允许、隔离模式和配额。
4. Adapter把标准请求转换为服务方请求；Secret Resolver在最后一跳注入API Key/签名。
5. 当前三个组件由数据面向GenB取得并短时缓存Actor Token，再按现有双Token合同调用；外部服务不强制理解Actor Token。
6. Adapter归一响应和错误，审计只记录元数据、耗时、结果和requestId。

### 场景C：配置发布或撤权

1. 管理员在GenB发布新版本；数据库提交后生成单调递增`configVersion`。
2. GenB最佳努力调用数据面失效Interface；数据面同时每2秒轮询版本作为兜底。
3. 数据面只在完整快照校验通过后原子替换L1，并写入Redis最近有效版本。
4. 用户/智能体撤权、实现停用等高风险变更目标5秒内生效；旧高风险授权不得使用15分钟降级窗口。

### 场景D：故障

- GenB不可用：新登录和新配置失败关闭；已有低风险会话/路由最多使用最近有效快照15分钟。
- Redis不可用：不创建新会话；已有L1只允许极短只读宽限，写操作失败关闭并告警。
- 上游超时：仅幂等读按策略重试一次；写请求除非有幂等键不得自动重试。
- Adapter熔断：返回统一503和可重试提示，不自动切换到未经绑定的另一实现。
- 数据面重启：会话从专用Redis恢复；配置从最近有效快照恢复并向GenB校验版本。

## Interface合同

### 浏览器与访问控制

| Interface | 用途 |
|---|---|
| `GET /agents/_auth/login?agentId=&returnPath=` | 发起统一登录；returnPath只能是同agent下相对路径 |
| `GET /agents/_auth/callback` | 消费一次性Code、建会话、设置Cookie |
| `POST /agents/_auth/logout` | 撤销网关会话并清Cookie |
| `GET /internal/agent-access/authorize` | 仅Nginx内部调用，返回上游和签名身份Header |
| `GET /.well-known/genb-gateway-jwks.json` | 智能体验证身份Token |

### 智能体与能力调用

- 固定入口：`POST /component-api/v1/capabilities/{capabilityCode}/operations/{operationId}:invoke`。
- `capabilityCode`使用14个稳定能力码；服务方名称不进入智能体合同。
- `operationId`必须来自已发布OpenAPI；未知操作返回404，未绑定返回403，停用/不健康返回503。
- 写操作要求`Idempotency-Key`；请求和响应默认JSON，流式能力由已发布`responseMode=SSE`显式声明。
- 身份从签名Token取得，正文中的`tenantId/userId/agentId`如存在必须忽略或拒绝。
- 统一采用RFC 9457 Problem Details字段：`type/title/status/detail/code/requestId/retriable`，不向调用方透传上游秘密或堆栈。

### GenB与数据面控制Interface

| Interface | 行为 |
|---|---|
| `GET /api/v1/internal/data-plane/config/version` | 返回最新版本和ETag |
| `GET /api/v1/internal/data-plane/config/snapshot` | 返回完整已发布快照，不含Secret正文 |
| `POST /api/v1/internal/data-plane/identity/exchange` | 网关机器身份交换一次性Code |
| `POST /api/v1/internal/data-plane/actor-token` | 为当前用户/agent/绑定签发短时Actor Token |
| `POST /api/v1/internal/data-plane/audits:batch` | 接收脱敏审计批次 |
| `POST /internal/cache/invalidate` | GenB提交后最佳努力通知，必须双向机器认证 |

接口名称在M0合同测试中可调整一次；Gate A后任何不兼容变化必须升版本并更新本计划。

## GenB数据模型与服务接入

平台固定能力与服务方实现分离：

- `capabilityCode`：GenB固定14能力之一。
- `providerServiceName`：服务方自由名称，仅展示和审计。
- `implementationCode`：GenB内唯一稳定标识。
- `adapterCode + adapterVersion`：选择已编译Adapter。
- `upstreamBaseUrl`：只允许管理员发布且通过网络白名单校验。
- `credentialRef`：指向网关Secret，不存秘密正文。
- `isolationMode`：`STATELESS`、`SUBJECT_KEYS`、`DEDICATED_INSTANCE`或`UNSUPPORTED_MULTI_USER`。
- `operationPolicy`：超时、幂等、大小、流式、重试和配额。
- `configVersion/status`：只有完整PUBLISHED快照可下发。

同事最低交付：服务地址、接口/OpenAPI或准确调用说明、认证方式、请求响应示例、错误/超时/并发说明、健康检查、隔离能力和联系人。Manifest由平台根据材料生成，不要求同事使用GenB项目名或实现GenB用户权限。

一期Adapter是代码审查后的编译期模块；不允许管理员上传脚本或表达式动态执行。新增Adapter需要数据面版本发布，但不需要修改每个智能体。

## 会话、缓存与状态规则

| 数据 | Key维度 | TTL/刷新 | 失效规则 |
|---|---|---|---|
| 网关登录会话 | 随机session hash | 8小时，可配置滑动过期 | 退出、用户禁用、凭证轮换立即撤销 |
| 用户访问智能体权限 | user＋agent＋policyVersion | L1 5秒、Redis 30秒 | 主动失效＋2秒版本轮询 |
| 智能体上游路由 | agent＋configVersion | L1 30秒、Redis 5分钟 | 发布/停用立即失效 |
| 组件绑定/Adapter | agent＋capability＋version | L1 30秒、Redis 5分钟 | 发布/停用立即失效 |
| Actor Token | user＋agent＋session＋bindingVersion | 最长5分钟 | 撤权事件立即删除；过期重新签发 |
| 身份Token | user＋agent＋session | 最长60秒 | 会话撤销后拒绝，agent必须校验exp/aud |
| 审计缓冲 | Redis Stream | 有界长度与批量确认 | 超限告警，不写正文 |

配置快照必须完整校验后原子替换，不能逐字段更新形成混合版本。高风险撤权目标5秒内生效；GenB不可用时低风险最近有效配置最多宽限15分钟，超过后失败关闭。

网关不保存智能体对话。对话是否长期保留由智能体或会话记忆能力负责，隔离键至少为`tenantId + agentId + userId + conversationId`。

## 安全设计

- CSRF：Cookie采用SameSite=Lax；所有网关自有写Interface验证Origin/Referer并使用一次性state；登出只接受POST。
- Header伪造：Nginx删除全部外来`X-GenB-*`、`X-Forwarded-*`敏感变体，再注入自己的值。
- SSRF：上游只能来自PUBLISHED快照；限制协议、主机、端口和网络区；禁止用户URL；重定向默认关闭或重新校验。
- 开放重定向：callback和returnPath必须是登记的同源地址或同agent相对路径。
- 重放：授权码单次消费；state绑定浏览器；身份Token短时且校验aud；写操作使用幂等键。
- Secret：数据库和配置快照只保存`credentialRef`；本地使用测试Secret文件；日志、响应、前端和Git不得出现正文。
- 最小数据：外部服务只收到执行所需正文和匿名`subjectKey/conversationKey`，默认不传用户名和门户Token。
- 路径安全：agentId和剩余路径分别解析，拒绝编码穿越、双重解码和跨agent returnPath。
- 绕过防护：生产上游端口只允许Nginx/数据面来源；本地以网络策略样例和直连负向测试固定要求。

## 智能体兼容分类

| 类型 | 接入方式 | 用户隔离结论 |
|---|---|---|
| 无状态智能体 | 只改GenB入口为`/agents/{id}/` | 可零代码改造；请求级隔离由网关保证 |
| 已支持用户/会话Header | 映射到网关身份Token或统一Header | 少量配置，需验证存储键 |
| 需要核心能力的智能体 | 使用统一能力Client，不实现SSO | 需修改调用地址，但不持有服务凭证 |
| 全局内存/公共目录的单用户智能体 | 按用户/会话独立实例，或最小修改存储键 | 未处理前不得声明多用户隔离 |
| 无法改造且有状态 | 标记`UNSUPPORTED_MULTI_USER` | 只允许受限单用户或暂不迁移 |

“能够从统一入口打开”不能作为“支持用户隔离”的证据。

## 质量目标与本地毕业指标

- 数据面应用在本地限制1CPU/1GiB，稳定测试期间无持续内存增长。
- 普通鉴权缓存命中P95小于10ms；组件网关自身新增P95目标小于50ms，不含上游耗时。
- 本地验证20活跃用户、100登录会话、20组件并发和目标SSE连接数。
- 正常业务请求不逐次访问GenB；配置版本轮询不高于每2秒一次/网关实例。
- 权限撤销和实现停用在本地端到端测试中5秒内生效。
- GenB不可用超过15分钟后失败关闭；恢复后自动更新到最新完整快照。
- 任何浏览器响应、日志、审计、测试快照和前端包中不得出现服务Secret、Actor Token或门户Token。
- 所有公开Interface具备requestId、稳定错误码和可观测耗时。

这些是本地毕业条件，不代表服务器容量已经通过；生产资源门禁由后续上线前检查计划负责。

## 修改范围与交付物

### 计划修改

- `genb-data-plane-gateway/`：新数据面应用、Adapters、测试、Dockerfile和本地Compose。
- `gen-b/gen-b-backend/`：控制面模型、显式迁移、网关身份、快照、Actor Token和审计批次。
- `gen-b/gen-b-console/`：外部实现、Adapter、路由、Secret引用、隔离模式和发布状态。
- `gen-b/gen-b-client/`：统一智能体入口及迁移状态提示。
- `control-system-test-agent/`：移除自身SSO责任的目标实现，改用统一能力Client；保留现有三种对话体验。
- 当前三个组件：只增加网关机器身份兼容和回归，不降低现有Actor隔离。
- `contracts/`：配置快照、身份Token、能力调用和Adapter合同。
- `docs/`、ADR、操作指南、兼容清单和完成报告。

### 明确不修改

- 不操作生产服务器、生产Nginx、生产Redis和生产数据库。
- 不实现其他同事负责的11个组件业务逻辑。
- 不动态执行服务方上传代码，不建立通用脚本运行平台。
- 不把所有旧智能体强行标记为多用户兼容。
- 不删除生产旧入口；本地完成迁移证据后由部署计划逐个删除。
- 不覆盖脏工作树无关修改，不执行破坏性Git操作。

### 交付物

- 替代ADR、威胁模型、OpenAPI/JSON Schema和错误目录。
- 数据面应用、三个现有Adapter、一个非标准Fake服务Adapter、统一能力Client。
- GenB显式数据库迁移、快照/失效/身份/审计Interface及管理页面。
- 本地Nginx样例、Redis/网关Compose、镜像和SBOM/Secret扫描结果。
- 智能体兼容性清单、服务方接入指南、逐点击验收指南和Gate F报告。

## 实施步骤与Gate

### M0：ADR、威胁模型、失败基线和合同

1. 保存现有直连、18714自有SSO和旧端口入口测试基线。
2. 新增替代ADR，固定选型、职责、后果和确认方式。
3. 写配置快照、身份Token、能力调用、错误和Adapter合同。
4. 先取得未授权、Header伪造、未知上游、未绑定、过期/撤权和跨用户失败测试。

Gate A：ADR和本文件一致；合同可机器校验；失败测试确实为红；未解决的安全问题有明确阻塞项，才允许实现。

M0实际证据（2026-08-12）：

- 新增`records/decisions/20260812-ADR-unified-data-plane-gateway.md`，仅替代智能体常态直连结论，保留十四组件独立交付和五系统分类。
- 新增`docs/security/UNIFIED_DATA_PLANE_GATEWAY_THREAT_MODEL.md`，T01-T12分别固定身份Header、SSRF、路径、重放、撤权、配置、Secret、隔离、CSRF、故障、审计和直连绕过风险。
- 新增数据面配置快照、身份Token、能力调用、Adapter、Problem Details及两份OpenAPI合同。
- `python -m unittest contracts.tests.test_data_plane_contracts -v`：6项通过。
- `python genb-data-plane-gateway/tests/test_m0_security_red.py -v`：8项按预期失败；裸端口由当前客户端代码直接证实，其余失败原因为本地数据面尚未实现/启动。
- 失败基线见`records/baselines/20260812-BASELINE-unified-data-plane-gateway-m0.md`；未操作服务器、生产Nginx、生产Redis或生产数据库。

Gate A结论：通过。该结论只允许进入M1，不代表任何网关业务能力已完成。

### M1：GenB控制面纵向切片

1. 先写迁移、发布状态、自由服务名、Adapter选择、Secret引用和快照版本失败测试。
2. 实现最小数据模型、显式迁移和内部Interface。
3. 实现网关机器身份、一次性Code交换和Actor Token签发。
4. 管理端只实现支撑首个外部服务接入的必要字段和校验。

Gate B：Java专项与相关全量、迁移前后、RBAC、旧版本拒绝、Secret不落库和管理端构建全部通过。

M1阶段中间记录（2026-08-12）：首个tracer bullet已完成红绿循环：

- RED：`DataPlaneConfigControllerTest`的2项测试均因目标Interface返回404失败。
- GREEN：新增`data_plane_config_state`单行状态、显式无外键迁移、配置版本Service和机器身份保护的版本Interface；返回`schemaVersion=1.0`、单调`configVersion=1`和ETag。
- 验证：`DataPlaneConfigControllerTest`与`CoreComponentSchemaConstraintTest`共3项通过。
- 当时尚未完成：完整快照、发布时版本递增、自由服务名/Adapter/Secret引用/隔离模式数据模型、旧版本拒绝、一次性Code交换、Actor Token、审计批次和管理端必要字段。

后续M1进度（2026-08-12）：

- 完整快照信封先以404形成RED，随后实现同一`configVersion`和ETag下的`agents/implementations/bindings`原子响应。
- 外部Implementation登记先因治理字段缺失形成RED，随后增加自由`providerServiceName`、`adapterCode + adapterVersion`、`credentialRef`、保守隔离模式和强类型operation policy；缺失隔离声明默认`UNSUPPORTED_MULTI_USER`。
- “登记→发布配置→绑定智能体→读取快照”关键路径先因版本不递增形成RED，随后将发布、回滚、Implementation状态和绑定变化集中接入悲观锁保护的单调版本；快照仅包含运行中路由、REGISTERED Implementation、PUBLISHED配置、ENABLED绑定和非空operation policy。
- 快照不包含`configJson`、配置`secretRefs`或Secret正文；只包含受控`credentialRef`。
- 新增第二份显式迁移`V20260812_02__add_data_plane_implementation_metadata.sql`，仍保持无跨服务物理外键。
- 相关Java组合回归37项通过；数据面合同6项通过；`git diff --check`无错误。
- 当时尚未完成：旧Schema版本拒绝、一次性Code交换、Actor Token内部Interface、审计批次、管理端必要字段/构建、真实本地迁移前后验证和Java相关全量。

M1完成证据（2026-08-12）：

- 一次性Code通过现有门户授权Interface签发，新增网关机器身份保护的`/api/v1/internal/data-plane/identity/exchange`；Code原子消费、重放401，旧`schemaVersion`在消费前400。
- 新增`/api/v1/internal/data-plane/actor-token`，每次签发均重新检查Session Grant、账号状态、智能体授权和已发布活动绑定；RS256 Token经JWKS公钥验签并固定tenant/user/agent/session/capability隔离claims，未绑定能力403。
- 新增`/api/v1/internal/data-plane/audits:batch`；事件采用闭合allowlist，未知Token/Secret字段400，主体仅接受SHA-256摘要并只保存64位摘要正文。
- 控制OpenAPI补齐三个写Interface的闭合请求/响应Schema，`schemaVersion=1.0`且`additionalProperties=false`；合同测试7项通过。
- 管理端注册表单增加自由服务名、Adapter编码/版本、Secret引用、隔离模式和首个operation policy，表格展示治理元数据；表单模型测试与Vite生产构建通过。
- 本地`127.0.0.1` PostgreSQL `genb_local.bank_agent_db`迁移前确认六列和两约束不存在；D盘备份后以单事务执行两份迁移，7条旧Implementation全部回填，非空/隔离约束、JSON数组和Secret引用检查均通过。
- Java全量`mvn test`：164项通过、0失败、1项既有Redis Testcontainers条件跳过；新增身份/审计专项7项、数据面组合专项13项均通过。未操作服务器、生产Nginx、生产Redis、生产数据库或运行容器。

Gate B结论：通过。下一步只能进入M2统一访问纵向切片，不能跳到服务器检查或生产部署。

### M2：统一访问纵向切片

1. 先写Cookie、登录、退出、撤权、Header清洗、SSRF、路径穿越、SSE/WebSocket失败测试。
2. 实现Gateway Session、Access Decision、Identity Token和JWKS。
3. 提供本地Nginx`auth_request`配置，让Nginx直传智能体字节流。
4. 用一个无状态Fake智能体和一个读取身份的Fake智能体验证两类接入。

Gate C：登录/退出/过期/撤权、两个用户两个智能体、伪造攻击和流式代理全部通过；浏览器看不到真实地址和内部Token。

M2完成证据（2026-08-13）：

- 新增Python ASGI网关，`Gateway Session`、`Access Decision`、RS256 Identity Token与JWKS按独立Interface实现；Cookie仅保存随机值，Redis Key仅保存SHA-256摘要，TTL为8小时，身份Token最长60秒。
- 登录state单次消费并绑定agent/returnPath；callback通过唯一网关机器身份交换M1一次性Code；退出验证同源Origin、撤销本地会话并调用新增的机器身份`identity/revoke`控制Interface。
- `identity/revoke`在GenB侧使用Redis Lua按`grantHash + agentId`原子匹配和删除；无机器身份401，重放401，控制OpenAPI增加闭合版本化Schema。
- 发布路由要求协议、主机、端口精确命中allowlist；开放重定向、跨agent路径、一次/二次编码穿越、用户上游Header均被拒绝或忽略。
- 本地Nginx 1.31.3真实`nginx -t`通过；`auth_request`只取得授权结果，Nginx关闭浏览器Header整体透传并按allowlist重建，直接转发SSE/WebSocket字节流，Python不代理智能体正文。
- 一个无状态Fake和一个验签读取身份Fake完成两用户两智能体实际回环验收；跨agent Cookie 401，任意`X-GenB-*`伪造和网关Cookie均未到上游，浏览器响应无上游地址和内部Token。
- M2测试12项通过；控制合同7项通过；Java全量167项通过、0失败、1项既有Redis Testcontainers条件跳过；Python compileall通过。只运行本地回环Nginx、独立16380 Redis和Fake，未操作服务器、生产配置、生产Redis或生产数据库。

Gate C结论：通过。下一步只能进入M3核心能力调用纵向切片，不能跳到服务器检查或生产部署。

### M3：核心能力调用纵向切片

1. 先写未绑定、停用、未知operation、Secret泄漏、隔离、幂等、超时和熔断失败测试。
2. 实现Capability Invocation、Adapter Registry、Secret Resolver和统一错误。
3. 依次接入短期、长期、规划三个Adapter，保持Actor Token合同。
4. 接入一个名称和请求格式完全不同的Fake外部服务，证明智能体无需变化。
5. 将18714改为统一能力Client，不再自己持有组件地址和外部凭证。

Gate D：四个Adapter、三种对话体验、两用户隔离、幂等、流式/非流式、限流和故障矩阵全部通过。

M3完成证据（2026-08-13）：

- 新增公开`Capability Invocation`深模块：短时Identity Token与智能体机器身份双校验、活动Gateway Session反查、发布绑定/operation校验、闭合调用信封、请求大小、逐签名主体限流、幂等重放/冲突、超时、熔断、JSON/SSE及统一Problem Details均在Adapter前后形成单一边界。
- 完整快照可原子编译为`PublishedCapabilityTable`；Secret只允许显式`env://NAME`或预登记`file://alias`解析，快照、响应和日志边界不包含Secret正文。Actor Token由Gateway Session Grant通过唯一网关机器身份向M1控制Interface即时签发。
- 新增短期记忆、长期记忆、规划推理和完全异构Fake四个M3 Adapter；另保留一个推理兼容Adapter供18714现有客户对话迁移。Adapter Registry只注册审查后的代码与固定版本，不支持上传脚本。
- 异构Fake真实HTTP回环使用`POST /v7/execute`、vendor media type和`X-Vendor-Key`，统一调用方仍只使用`FEEDBACK_LOOP/summarize`；两个用户得到不同SHA-256匿名主体，响应不含用户标识、Secret或真实端口。
- 18714 Web运行时改用`DATA_PLANE_GATEWAY_URL`和统一`GatewayCapabilityClient`；组件地址不再来自Component Session响应，外部服务Secret和Actor Token不再进入智能体。短期对话、长期写入/跨会话检索、规划分析六次调用均只命中`/component-api/v1/capabilities/...`。
- M3网关专项22项通过；M2+M3选择性回归32项通过；控制合同7项通过；18714全量66项通过；真实Redis主体反查/撤销1项通过；Python compileall和`git diff --check`通过。M0故意保持红色的历史基线脚本不作为后续Gate回归套件。
- 只运行本地回环Fake和独立Redis；未操作服务器、生产Nginx、生产Redis、生产数据库，也未提交或推送脏工作树。

Gate D结论：通过。下一步只能进入M4缓存、失效、审计与恢复，不能跳到服务器检查或生产部署。

### M4：缓存、失效、审计与恢复

1. 先写混合版本、撤权延迟、GenB/Redis/上游故障和审计背压测试。
2. 实现L1＋Redis、完整快照原子替换、主动失效和2秒轮询兜底。
3. 实现Actor Token缓存、Redis Stream审计缓冲和GenB批量提交。
4. 验证15分钟宽限边界、高风险失败关闭和重启恢复。

Gate E：缓存一致性、5秒撤权、15分钟上限、无无限重试、Secret扫描和故障注入全部通过。

M4完成证据（2026-08-13）：

- 新增`ControlSnapshotModule`，将路由与能力绑定从同一闭合快照、同一`configVersion`原子编译；混合版本或不兼容快照不会替换LKG。Redis保存完整快照及抓取时间，进程重启先恢复LKG，再与GenB最新版本收敛。
- 运行时每2秒检查控制面版本；高风险决策在快照失联超过5秒后失败关闭，低风险只允许使用不超过15分钟的LKG。主动失效Interface只接受机器Bearer身份及`CONFIG/CAPABILITY/SESSION/USER_AGENT/AGENT`闭合范围。
- Gateway Session增加5秒L1与Redis主体/用户智能体/智能体索引；撤权先清L1并写拒绝墓碑，即使Redis删除失败，恢复后的旧记录也不能重新授权。GenB在配置发布和用户/角色撤权事务提交后发送失效通知。
- Actor Token按租户、用户、智能体、会话、能力及绑定版本缓存，最长5分钟且预留5秒安全边界；失效事件精确清除。审计使用有界Redis Stream，单批最多100条，只有GenB完整接收才删除；背压时明确计数丢弃，不无限增长。
- 仅幂等`READ`允许一次补偿重试，其他操作单次调用；持续故障严格停止在两次。Redis、GenB、上游、审计背压、重启恢复、15分钟边界和混合版本故障注入均有自动化覆盖。
- 网关M2-M4回归49项通过、1项本地Nginx条件跳过；数据面合同7项、18714全量66项、GenB Java全量169项通过（1项既有Redis Testcontainers条件跳过）；Python compileall、`git diff --check`及生产源码Secret特征扫描通过。
- 只运行本地独立Redis；未操作服务器、生产Nginx、生产Redis、生产数据库，也未提交或推送脏工作树。

Gate E结论：通过。下一步只能进入M5本地总验收、兼容清单和交付，不能跳到服务器检查或生产部署。

### M5：本地总验收、兼容清单和交付

1. 本地运行Nginx、GenB、数据面、专用Redis、18714、三个组件和Fake外部服务。
2. 浏览器完成统一登录、刷新、退出、短期两轮、长期跨会话和Skill先澄清后生成。
3. 完成20用户/20组件并发、SSE、内存稳定性和新增延迟测试。
4. 按五类智能体形成兼容清单；不兼容项不得伪装通过。
5. 核对代码、OpenAPI、迁移、ADR、指南和计划一致，形成完成报告与待部署产物哈希。

Gate F：全部自动化、浏览器、安全、性能、故障、文档和兼容性证据通过；跳过项不涉及上线必需能力，才允许进入上线前检查计划。不得跳过该计划直接部署。

M5完成结论（2026-08-13）：

- 已完成闭合运行工厂、健康检查、非root只读容器、兼容清单、20用户/20组件并发、20条SSE、500次调用内存稳定性和确定性本地浏览器链路。
- 最终回归：网关常规绿灯53项、合同9项、18714智能体67项、Runtime 47项、三组件82项、GenB Java 170项通过（1项既有环境条件跳过），GenB中英文前端生产构建通过。
- 镜像约28 MB，Docker Scout扫描31个包，Critical/High为0；SBOM、SARIF和待部署产物哈希已记录在M5阶段报告。
- 已在同一窗口运行Nginx、真实GenB、数据面、专用Redis、18714、短期记忆、长期记忆、规划推理和Runtime Fake Provider；双用户真实Chrome完成短期、长期、Skill、刷新、隔离和退出矩阵。

Gate F结论：通过。允许进入上线前检查计划，仍禁止跳过该计划直接生产部署；完成证据见`records/reports/20260813-REPORT-unified-data-plane-gateway-m5.md`。

## 验证矩阵

| 层级 | 必测内容 | Gate条件 |
|---|---|---|
| 静态合同 | OpenAPI、Schema、operationId、错误码、JWT claims、快照版本 | 全部一致 |
| GenB | 迁移、RBAC、发布、快照、失效、网关身份、Actor Token、审计 | 专项及相关全量通过 |
| 访问控制 | SSO、Cookie、退出、撤权、代理、SSE/WS、Header/路径攻击 | 正负向全部通过 |
| 能力调用 | 四Adapter、Secret、绑定、隔离、幂等、超时、限流、熔断 | 正负向全部通过 |
| 缓存故障 | 命中、原子更新、5秒撤权、15分钟上限、Redis/GenB恢复 | 不出现混合版本和越权 |
| 浏览器 | 两用户、多会话、三个非技术对话体验、刷新和退出 | 无控制台错误和秘密暴露 |
| 性能资源 | 20用户、20组件并发、SSE、P95、1GiB内存限制 | 达到质量目标 |
| 安全 | Secret扫描、依赖扫描、SSRF/CSRF/重放/开放重定向 | 无未处置高风险项 |

## 升级、降级与版本偏差

- 数据库只做兼容新增；部署切流前不删除旧字段、旧绑定或旧Component Session Interface。
- 数据面同时支持当前三个组件现有Interface版本；Adapter按`adapterCode + version`选择。
- GenB快照版本高于网关支持版本时拒绝加载并保留最近兼容快照；低于最低版本时失败关闭。
- 本地使用功能开关分别启用访问模块和能力模块；回退时可恢复旧直连基线，但不形成长期双版本承诺。
- 新入口生产验收后，旧入口删除发生在部署计划，不在本地计划提前操作。

## 风险、停止条件与遗留边界

- Nginx动态上游配置可能形成SSRF；不能证明只接受发布白名单时停止Gate C。
- Gateway Identity Token只有在上游不能被公网绕过时可信；本地只验证合同，生产网络是部署Gate。
- 外部有状态服务没有隔离能力时不得进入多用户Gate D。
- 单物理进程节省资源但共享故障域；一期接受，扩容后可按内部Interface拆分。
- Redis同时承载会话、缓存和审计缓冲；必须使用前缀、TTL和有界Stream，任何无界增长阻塞Gate E。
- Python反向代理所有字节会增加资源风险，因此一期明确由Nginx承载智能体流量；实现不得偏离。
- 当前计划不解决真实生产高可用；本地Gate F不能替代服务器检查Gate D。

## 回滚与记录规则

- 每个里程碑只修改当前纵向切片，回滚只撤销本轮精确文件和迁移，不覆盖用户工作树。
- 迁移失败优先向前修复；本地数据库必须先备份，禁止用生产数据库补证据。
- Gate A前不得写实现；一次只有一个里程碑处于执行中。
- 方案、接口、缓存TTL、安全语义或兼容分类变化时，先更新本文件和ADR。
- Gate F完成后更新`CURRENT_TASKS.md`、索引、设计/开发/操作文档并新增完成报告；随后才启动上线前检查计划。
