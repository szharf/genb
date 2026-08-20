# 统一数据面网关智能体兼容清单

- 日期：2026-08-13
- 状态：M5本地核对
适用范围：GenB本地已知智能体源码，不代表生产实例已经迁移

## 判定规则

“能够从统一入口打开”与“支持多用户隔离”分别判定。只有身份来源可信、持久化键包含签名主体、核心能力只走统一Client且不存在裸端口绕过时，才标记为多用户兼容。

| 对象 | 类型 | 统一入口 | 用户隔离结论 | M5处置 |
|---|---|---|---|---|
| `core-component-demo-agent`（18714） | 需要核心能力 | 已接入Gateway Session与Identity Token | `tenant/user/agent/conversation`经网关签名主体传递，兼容 | 已移除网关模式下的二次登录；短期、长期、规划、推理均走Capability Client |
| M2无状态Fake | 无状态 | 可零代码代理 | 请求级兼容 | 保留为Nginx字节流与Header清洗验收对象 |
| M2身份感知Fake | 已支持身份 | 接收RS256 Identity Token | 请求级兼容 | 保留为签名身份验收对象 |
| `bank-agent-runtime` | 已有tenant/user字段 | 尚未完成网关入口核对 | 有隔离字段，但身份真源和全部存储键未完成M5审计 | `NEEDS_REVIEW`，不得据字段存在宣称兼容 |
| 对公客户准入与尽调FastAPI | 接受可选`user_id` | 尚未接入 | `user_id`当前属于请求字段，不是网关签名真源 | `UNSUPPORTED_MULTI_USER`，迁移前仅限受控单用户 |
| SDD设计智能体 | 自有用户/项目数据库 | 尚未接入 | 项目归属与网关主体映射未审计 | `NEEDS_REVIEW`，不得开放统一多用户入口 |
| SDLC AI Coding | 项目型有状态Flask | 尚未接入 | 项目/聊天记录未证明按签名用户隔离 | `UNSUPPORTED_MULTI_USER` |
| SDLC AI Testing | 项目型有状态Flask | 尚未接入 | 项目、执行、报告未证明按签名用户隔离 | `UNSUPPORTED_MULTI_USER` |

## 迁移最低条件

1. 浏览器只持有Gateway Session Cookie，智能体不再建立第二套SSO。
2. 智能体只接受Nginx重建的可信身份；上游端口受网络策略保护，不能被浏览器绕过。
3. 所有用户数据键至少包含`tenantId + userId + agentId`；会话数据再包含`conversationId/sessionId`。
4. 核心组件地址、Secret和Actor Token不进入智能体；智能体只调用`/component-api/v1/capabilities/...`。
5. 通过两用户交叉访问负向测试、撤权测试和持久化数据隔离测试后，才能将状态改为兼容。
