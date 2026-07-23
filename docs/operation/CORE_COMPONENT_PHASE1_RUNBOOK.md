# 核心组件一期运行手册

## 1. 适用范围

本手册只覆盖一期三个真实组件：Runtime System 的 Inference Engine Service，以及 Control System 的 Short-term Memory、Long-term Memory。其他11张卡仍为`PLANNED`，不得按本手册宣称已上线。

## 2. SLO与容量基线

| 服务 | 可用率目标 | 延迟目标 | 错误率 | 初始单实例保护 |
|---|---:|---:|---:|---|
| Runtime Inference | 99.5%/月 | 非流式p95≤10s | 5xx<1% | 并发32、120请求/60s/凭证、输入262144字符 |
| Control System | 99.9%/月 | 同步Interface p95≤2s | 5xx<0.5% | 并发64、600请求/60s/进程、body≤262144字节 |

初始值是安全上限，不是容量证明。必须用真实Provider、目标硬件和脱敏高保真数据完成基准、峰值和稳定性测试后才能调整。多副本总限流必须由网关或共享限流层实施。

## 3. 值班检查

1. 检查`/health/live`，失败表示进程或路由故障。
2. 检查`/health/ready`；Control必须同时看到`shortTermStore=UP`和`longTermStore=UP`，Runtime生产不得显示Fake Provider。
3. 检查Dashboard中的请求率、p95、5xx、容量拒绝和长期提取队列。
4. 只使用`requestId/traceId`关联事件；不得复制用户正文、服务凭证、Actor Token或数据库DSN到工单。

## 4. 告警处置

### Runtime Inference 高错误率

- 对比Provider健康、429、5xx和非法响应错误码；不查看或转存Provider原始错误正文。
- Provider故障时停止扩大灰度；有已验证备用路由才允许切换，否则返回可重试错误。
- 核对最近路由配置版本和Implementation版本，必要时回滚到上一不可变版本。

### Runtime Inference 高延迟

- 检查并发、Provider延迟和连接池等待；确认是否同时发生容量拒绝。
- 不通过无限增加超时掩盖问题。先停止灰度、降低流量，再按容量报告扩容。

### Control System 高错误率

- 分别检查GenB内省/JWKS、Redis、PostgreSQL和Runtime依赖。
- 身份依赖异常必须保持fail-closed，不得临时关闭双凭证校验。
- PostgreSQL或Redis异常时停止写流量，按只读/降级策略处置。

### Control System 高延迟

- 按operation区分短期提交、上下文准备、长期搜索和提取提交。
- 检查Redis延迟、PostgreSQL慢查询、连接池和配置缓存，不记录查询正文。

### 长期记忆任务积压

- 检查Worker进程、最老任务年龄、租约和Runtime结构化提取错误。
- 不批量删除任务。先修复依赖并让过期租约恢复；达到重试上限的任务保留审计状态。

### 容量或限流拒绝

- 区分`input_limit`、`body_size`、`rate_limit`和`concurrency`。
- 先确认异常流量、重试风暴和单个凭证行为，再决定限流调整或扩容。
- 所有上限变更走不可变配置版本、灰度和回滚，不直接在线改代码默认值。

## 5. 安全事件

- 凭证疑似泄漏：在GenB吊销该凭证，停止相关绑定，验证旧凭证立即内省为inactive，再发放新凭证。
- 越权或跨域数据：立即停用对应Implementation/绑定，保留审计，不直接删除证据；按tenant/user/agent范围核查。
- 数据污染：停止Long-term写入和Worker，记录污染时间窗与scope；使用软删除/状态修复脚本，不执行无条件DELETE。
- 指标与日志发现秘密：停止采集和下游转发，按数据泄漏流程处置并修复脱敏；不得只修改Dashboard隐藏。

## 6. 回滚顺序

1. 停止扩大灰度并保存当前版本、配置、绑定和告警快照。
2. 优先回滚GenB绑定/配置到上一不可变已验证版本。
3. 再回滚网关路由和服务镜像digest；不得使用浮动tag。
4. 数据迁移使用expand/contract和前向修复。未经验证不得反向执行破坏性DDL。
5. 验证健康、鉴权、A/B隔离、敏感拒绝、短期召回和长期搜索/软删除。

## 7. 尚未关闭的上线门禁

- Direct Provider真实调用、费用上限和数据出境/训练/日志保留合规签字。
- 生产PostgreSQL、Redis、Secrets Manager、网关、证书、备份RPO/RTO和owner确认。
- 目标环境基准/峰值/72小时稳定性、渗透、依赖漏洞和灾难恢复正式演练。
- 不可变镜像digest、完整解析依赖SBOM和漏洞扫描报告。

