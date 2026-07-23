# GenB服务凭证与组件会话Iteration 5报告

## 1. 背景

Iteration 4已经完成Implementation、配置和绑定的治理状态机。智能体要真正调用五大系统的数据面，还需要机器身份和代表当前用户的短时授权；如果直接把长期API Key交给每次组件调用，泄漏半径、吊销延迟和身份混淆都会过大。

## 2. 目标

建立`管理员签发服务凭证 → 登录Actor用凭证换取组件会话 → 智能体按绑定快照调用数据面`最小闭环。GenB只处理低频签发与解析，高频组件调用不回调GenB。

## 3. 公开Interface

| 方法 | 路径 | 权限/身份 | 说明 |
|---|---|---|---|
| POST | `/v1/service-credentials` | `credential.issue` | 为逻辑智能体签发凭证，secret只返回一次。 |
| GET | `/v1/service-credentials?agentId=...` | `credential.issue` | 只返回元数据和公开前缀。 |
| GET | `/v1/service-credentials/audits` | `credential.issue` | 查询最近200条脱敏凭证审计。 |
| POST | `/v1/service-credentials/{id}:revoke` | `credential.revoke` | 立即吊销，重复操作幂等。 |
| POST | `/v1/client/agents/{agentId}/component-session` | 登录Actor+智能体使用权+服务凭证 | 返回短时Actor Token和组件绑定快照。 |

组件会话交换使用：

```text
Authorization: Bearer <GenB login token>
X-Agent-Credential: gmb_live_<keyId>_<random>
```

选择直接API Key交换而不是HMAC请求签名，是因为数据库只保存bcrypt哈希；哈希无法验证HMAC。若未来需要请求签名，应升级为私钥签名、mTLS或工作负载身份，不能可逆保存client secret。

## 4. 凭证安全

- secret随机主体来自`SecureRandom`的32字节熵并使用Base64URL编码。
- 数据库保存`keyId`、前缀、bcrypt哈希、scope、状态和生命周期元数据，不保存secret。
- 默认有效期90天，可由签发请求指定，最大365天。
- 篡改、过期、吊销、agent不匹配或hash不匹配统一返回无效，不暴露具体校验环节。
- 每个scope必须引用固定14组件目录中的真实组件。
- 签发、吊销审计不包含secret、hash或完整请求正文。

## 5. 组件会话安全

- 当前Actor必须通过既有`AgentGrantService`智能体使用权判断。
- 只解析请求集合内状态为`ENABLED`的绑定，Implementation必须为`REGISTERED`，配置必须为`PUBLISHED`。
- 服务凭证必须具有对应`component:<component-code>:<operation>` scope。
- Actor Token默认600秒，并强制限制在60—900秒。
- Claims包含`tokenType=COMPONENT_SESSION`、`jti`、组件会话ID、Actor类型/用户、`agentId`、`sessionId`、credential key、有效scope和绑定快照。
- 组件会话使用从登录签名秘密按用途派生的独立密钥；数据面获得组件校验密钥后不能用它签发GenB登录Token。
- 登录过滤器仍检查token用途，组件Actor Token不能访问核心组件管理Interface。

## 6. 测试与验证

逐项通过真实登录、JWT、Controller、Module和H2 JPA公开HTTP链路执行RED→GREEN：

1. 凭证签发最初404。
2. 凭证吊销最初404。
3. 组件会话最初404。
4. Actor Token最初可被误当成管理登录Token，测试得到200；用途隔离后变为403。
5. 未知组件scope最初被接受；目录校验后变为400。
6. 凭证审计最初404；查询Interface完成后通过。

最终Surefire结果：14个报告，101项测试，0失败，0错误，0跳过。`git diff --check`通过；源码复核确认secret只进入签发响应和bcrypt匹配路径，审计与列表不包含secret/hash。

## 7. 未包含范围

- 未实现凭证轮换和旧凭证宽限期。
- 未实现组件会话在线吊销或jti黑名单；已签发Token最长继续有效15分钟。
- 未建立可信tenant映射，因此本轮Claims包含当前GenB用户但不伪造tenantId；记忆数据面接入前必须补齐。
- 当前采用用途派生HMAC密钥；多实例生产建议升级非对称签名/JWKS、OAuth2或工作负载身份。
- 未提供显式数据库迁移，未连接远程PostgreSQL/Redis，未开发Vue页面，未部署。
- 未提交`target`、Vite缓存和中英文构建产物。

## 8. 下一步

优先补M3显式数据库迁移、凭证轮换、非对称签名/JWKS和tenant来源，再实现健康快照/TestRun与管理页面。上述身份门禁完成后，进入M4 Control System短期记忆数据面更稳妥。
