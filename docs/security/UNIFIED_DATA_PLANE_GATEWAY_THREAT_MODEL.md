# GenB统一数据面网关威胁模型

- 日期：2026-08-12
状态：M0基线；任何信任关系、身份、缓存或公开Interface变化必须同步更新

## 保护资产

- 门户用户身份、授权和会话。
- 网关机器凭证、服务Secret、Actor Token及签名私钥。
- 智能体上游地址、组件绑定和完整配置快照。
- `tenantId + agentId + userId + conversationId`隔离语义。
- 脱敏审计的完整性、顺序和可追溯性。

## 信任区域与数据流

| 区域 | 信任结论 | 允许输入 | 必须拒绝或重建 |
|---|---|---|---|
| 浏览器 | 不可信 | Cookie、同agent相对路径、业务正文 | 所有身份Header、上游URL、Actor Token、Secret |
| Nginx | 受控代理 | 网关鉴权结果、已发布路由 | 删除外来`X-GenB-*`和敏感`X-Forwarded-*`后重建 |
| 数据面应用 | 受信数据面 | GenB完整快照、Redis会话、机器身份 | 任意用户URL、正文身份、未发布或混合版本配置 |
| 智能体 | 受限工作负载 | 短时签名身份Token、统一能力Interface | 外部服务Secret、门户Token、任意实现地址 |
| 外部服务 | 最小信任 | 执行所需正文、匿名隔离键、服务自身认证 | 网关Cookie、门户Token、无关用户资料 |
| GenB | 控制面真源 | 治理元数据、版本、授权和审计批次 | 高频对话/文件正文、Secret正文 |

## 威胁与控制

| ID | 威胁 | 主要控制 | 失败/停止条件 | 验证阶段 |
|---|---|---|---|---|
| T01 | 浏览器伪造身份Header | Nginx删除后重建；网关只信签名Token | 任一外来身份Header到达上游 | M0红、Gate C绿 |
| T02 | SSRF或任意上游 | 仅完整PUBLISHED快照；协议/主机/端口/网络白名单；禁重定向 | 用户输入可改变上游 | M0红、Gate C/D绿 |
| T03 | 开放重定向/路径穿越 | returnPath限同agent相对路径；单次解码并拒绝穿越 | 可跳出`/agents/{id}/` | M0红、Gate C绿 |
| T04 | 授权码、Token或写请求重放 | code单次消费、state绑定、短时aud、幂等键 | code可二次交换或写请求重复生效 | Gate C/D |
| T05 | 撤权后缓存继续放行 | 主动失效＋2秒版本轮询；高风险失败关闭 | 撤权超过5秒仍可访问 | M0红、Gate E绿 |
| T06 | 混合配置版本或旧配置无限使用 | 完整校验后原子替换；低风险宽限最多15分钟 | 快照字段跨版本混用 | Gate E |
| T07 | Secret/Token泄漏 | 只保存`credentialRef`；末跳注入；响应/日志/审计扫描 | 正文进入Git、日志、浏览器或审计 | M0红、Gate B-E绿 |
| T08 | 跨用户有状态数据共享 | 强制隔离键、独立实例或`UNSUPPORTED_MULTI_USER` | 无隔离能力却宣称多用户 | M0红、Gate D绿 |
| T09 | CSRF | SameSite=Lax；写Interface验证Origin/Referer；登出仅POST | 跨站写操作成功 | Gate C |
| T10 | 上游故障放大 | 幂等读至多重试一次；写入不自动重试；超时、熔断、背压 | 无限重试或连接泄漏 | Gate D/E |
| T11 | 审计缓冲无界增长或包含正文 | Redis Stream有界、批量确认、超限告警、字段白名单 | 内存/磁盘无界或记录正文 | Gate E |
| T12 | 绕过统一入口直连上游 | 生产网络仅允许Nginx/数据面来源 | 浏览器可访问真实上游 | 部署Gate C/D |

## 身份与秘密规则

- 浏览器Cookie只保存随机会话标识；服务端保存会话，Cookie为HttpOnly、SameSite=Lax、Path=/agents，生产启用Secure。
- Identity Token最长60秒，必须包含`iss/sub/aud/exp/iat/jti/tenantId/userId/agentId/sessionId`，智能体校验签名、audience和过期。
- Actor Token最长5分钟，仅数据面与当前三个组件可见；撤权事件删除缓存。
- 数据库、快照、前端和普通配置只保存`credentialRef`，不保存Secret正文。
- 审计仅记录主体匿名标识、agent、能力、operation、绑定版本、结果、耗时和requestId，不记录对话或文件正文。

## 剩余风险

- 一期数据面和Redis均为单实例，只承诺可恢复，不宣称高可用。
- 本地M0无法证明生产上游不可绕过；该项是生产部署硬门禁。
- 未交付隔离说明的外部有状态服务不能进入多用户试点。
