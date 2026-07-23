# 核心组件真实测试智能体 Iteration 11 实施报告

## 任务：完成单代码多实例测试智能体与Short-term Memory真实端到端验收

### 1. 背景

Iteration 9已经实现Control System Short-term Memory，Iteration 10已经让GenB通过RS256 Actor Token、JWKS和服务凭证内省向数据面提供可信身份。但此前只有各项目内的自动测试，没有一个真实智能体从GenB换取组件会话后调用Control System，也没有用Agent A/B证明控制面绑定与数据面隔离能共同成立。

### 2. 目标

交付一套专用测试智能体代码，通过配置运行A/B两个逻辑实例，真实贯通GenB控制面、组件身份、Control System和Redis；让后续长短记忆开发都能重复使用同一验收入口。

### 3. 范围

本次完成：

- 新建`control-system-test-agent`独立工程和CLI。
- 实现GenB组件会话客户端、Control System短期准备/提交/清理客户端。
- 实现确定性测试回答器、准备失败降级和提交失败告警。
- 实现追加式开发环境初始化脚本，由GenB签发A/B、未绑定和只读四份独立服务凭证。
- 实现真实A/B验收器，覆盖连续召回、会话隔离、智能体隔离、错凭证、未绑定、scope不足和绑定停用/恢复。
- 用独立端口启动最新GenB与Control System，连接既有开发PostgreSQL和本地Redis DB 14。
- 验收结束只删除本轮新增Redis键，不删除既有远程数据库数据；联调进程验证后精确停止。

本次不做：

- 不接真实模型Provider；确定性回答器只隔离验证记忆链，不能替代后续模型/摘要验收。
- 不实现Long-term Memory、提取Worker、管理端测试台、监控和生产部署。
- 不新建数据库表，因此没有新增物理外键；远程库只追加`memory-test-*`智能体、实现、配置、绑定和凭证记录。
- 不把测试私钥、用户Token、服务凭证、内部Token或Redis密码写入Git和报告。

### 4. 完成标准

- [x] 客户端传递用户JWT、服务凭证、Actor Token、requestId和幂等键。
- [x] HTTP超时和上游错误映射不保留请求/响应正文与认证秘密。
- [x] 一套代码运行A/B，两个实例拥有不同`agentId`和服务凭证。
- [x] Agent A同会话召回2条历史消息；Agent A换会话和Agent B使用同名session均召回0条。
- [x] 错配服务凭证、未绑定智能体、只读scope和停用绑定全部fail-closed。
- [x] 真实GenB、Control System、开发PostgreSQL与Redis联调通过。
- [x] Redis测试键HMAC化，本轮新增10个键精确清理后残留为0。
- [x] 三项目全量回归、旧SDK扫描、秘密扫描、记录和精确提交完成。

### 5. 执行计划

| 顺序 | 工作 | 状态 | 验证 |
|---|---|---|---|
| 1 | 从详细实施指南固化测试智能体边界 | 已完成 | 单代码多实例、薄HTTP客户端和降级规则一致 |
| 2 | RED→GREEN实现客户端与编排Module | 已完成 | 8项测试通过 |
| 3 | 编写可重复的初始化与A/B验收器 | 已完成 | 凭证只落入Git忽略目录，证据不含秘密 |
| 4 | 启动独立GenB/Control并联调 | 已完成 | 18581/18701健康，9项真实检查通过 |
| 5 | 全量回归、安全扫描和提交 | 已完成 | Java 108、Control 21、Agent 8；代码提交`b703819` |
| 6 | 更新任务、计划、索引和报告 | 已完成 | 当前报告与反向索引可追溯 |

### 6. 当前进度

- 已完成：Iteration 11全部代码、自动测试和真实联调门禁。
- 已完成：测试智能体使用一套代码；复制逻辑实例只修改运行时`agentId`与独立服务凭证。
- 已完成：GenB是服务凭证唯一签发方，Test Agent不自行生成业务凭证。
- 下一步：Iteration 12补Short-term Memory摘要、动态配置获取、管理端测试台、指标和故障演练；随后进入Long-term Memory。

### 7. 验收记录

自动测试：

- [x] GenB Maven全量测试：`108 tests, 0 failures, 0 errors, 0 skipped`。
- [x] Control System全量测试：`21 passed`，含真实Redis合同测试。
- [x] Test Agent测试：`8 passed`，并完成`compileall`。
- [x] Test Agent源码、测试、脚本和配置示例无旧Runtime SDK引用。
- [x] 固定密码、私钥正文和服务凭证明文模式扫描无命中。

真实联调：

- [x] 最新GenB JAR在`127.0.0.1:18581/api`启动并连接开发PostgreSQL，Actuator健康为`UP`。
- [x] Control System在`127.0.0.1:18701`启动，以GenB内省/JWKS模式连接，ready为`UP`。
- [x] `agentAContinuousRecall`、`sessionIsolation`、`agentIsolation`通过。
- [x] `wrongCredentialDenied`、`unboundAgentDenied`、`insufficientScopeDenied`通过。
- [x] 绑定停用时组件会话被拒绝，`finally`恢复绑定后状态正常。
- [x] Redis原始tenant/agent/session不出现在键中；新增10键精确删除后残留0。
- [x] 验收专用18581/18701进程已按可执行文件和命令行校验后停止；既有8581和6379未停止。

提交：

- 父仓库：`b703819`（`feat: add control system test agent`）。
- GenB本轮无源码改动，继续使用Iteration 10提交`ef0a627`。
- Control System本轮无源码改动，继续使用Iteration 10提交`add0e13`中的身份Adapter实现。

### 8. 风险和遗留问题

1. 确定性回答器用于隔离验证组件链，不代表真实模型调用、提示构造或摘要质量已验收。
2. 测试初始化在开发PostgreSQL中保留`memory-test-*`治理记录和已签发凭证记录；这是遵循“不轻易删除远程数据”的追加式证据，旧凭证后续应通过GenB吊销而不是直接删库。
3. Actor Token过期和JWT异常矩阵由GenB/Control自动测试覆盖；真实E2E没有等待5分钟做过期演示，避免把测试时长引入每次验收。
4. 当前Test Agent是CLI和自动验收器，管理端可视化测试台仍属于M6/Iteration 12。
5. 尚未实现Long-term Memory和完整RAG，14张卡中只有已交付真实实现的组件可以标为可用。
