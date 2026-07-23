# 核心组件一期上线门禁矩阵基线

> 状态口径：`PASS`表示已有可重复证据；`IN_PROGRESS`表示本轮正在补齐；`BLOCKED_EXTERNAL`表示需要组织责任人、生产资源或真实Provider，不能由本地代码伪造关闭。

| ID | 门禁 | Owner | 状态 | 当前证据/出口 |
|---|---|---|---|---|
| P1-01 | 五大系统14张固定卡，3张真实、11张PLANNED | GenB | PASS | 管理端目录、自动测试和浏览器截图 |
| P1-02 | 三组件注册/配置/绑定/鉴权 | GenB/Control/Runtime | PASS | Iteration 8—13测试与E2E |
| P1-03 | Runtime六类Interface契约 | Runtime | PASS | Runtime公开Interface和OpenAPI测试 |
| P1-04 | Direct Provider真实调用 | 模型负责人 | BLOCKED_EXTERNAL | 需选型、凭证、费用和合规后执行真实门禁 |
| P1-05 | Short-term契约、TTL、预算、摘要、幂等、隔离 | Control | PASS | Iteration 9/12/13回归 |
| P1-06 | Long-term提取、过滤、去重、检索、过期、删除 | Control | PASS | 远程PG合同与四跳E2E |
| P1-07 | 密码/凭证零泄漏 | 安全/研发 | IN_PROGRESS | 自动扫描已通过；仍需生产日志/追踪/渗透证据 |
| P1-08 | 菜单/路由/API权限一致 | GenB | PASS | 管理端权限与后端测试 |
| P1-09 | Redis/PostgreSQL/Runtime故障降级 | Control | PASS | Adapter、ready、Worker重试测试 |
| P1-10 | 限流、并发、输入和成本上限 | Runtime/Control/SRE | IN_PROGRESS | 单进程保护已实现；网关集群配额和费用上限待外部方案 |
| P1-11 | SLO指标、Dashboard、告警和runbook | SRE/研发 | IN_PROGRESS | 本地指标与首版资产已实现；待监控平台导入和owner确认 |
| P1-12 | PostgreSQL/Redis生产拓扑与RPO/RTO | DBA/SRE | BLOCKED_EXTERNAL | 需生产资源、备份策略和恢复验收 |
| P1-13 | Secrets Manager、TLS/mTLS与网关 | SRE/安全 | BLOCKED_EXTERNAL | 需产品选型、证书和生产网络方案 |
| P1-14 | 身份吊销、越权、注入和秘密测试 | 安全/研发 | IN_PROGRESS | 吊销/越权已有；攻击集和正式渗透待完成 |
| P1-15 | 镜像digest、完整SBOM和漏洞扫描 | DevOps/安全 | BLOCKED_EXTERNAL | 本机缺SBOM/漏洞工具与批准镜像仓库 |
| P1-16 | OpenAPI、配置Schema、迁移可追溯 | 研发 | PASS | 契约测试、显式SQL、无物理FK检查 |
| P1-17 | 配置/绑定/路由/凭证回滚 | GenB/SRE | IN_PROGRESS | 控制面能力已有；待形成自动演练证据 |
| P1-18 | 数据污染与备份恢复演练 | DBA/Control | BLOCKED_EXTERNAL | 必须在批准的恢复环境执行，不覆盖开发共享库 |
| P1-19 | 基准、峰值和72小时稳定性 | QA/SRE | BLOCKED_EXTERNAL | 需目标硬件、真实Provider和容量目标 |
| P1-20 | Provider与外部数据合规签字 | 合规/安全/模型负责人 | BLOCKED_EXTERNAL | 书面签字是上线硬门禁 |

当前结论：一期功能纵向切片已完成，但生产上线门禁尚未关闭；不得标记为“可生产上线”。

