# ADR：五个系统仅作分类，十四个核心组件分别提供独立服务

- 状态：已采纳
- 日期：2026-08-05
- 决策人：项目负责人
- 范围：GenB核心组件目录、组件服务接入、团队分工和部署拓扑
- 替代：`20260723-ADR-control-system-component-service.md`中“一个系统服务承载多个核心组件”的默认部署结论

## 背景

十四个核心组件由不同同事分别负责开发、测试和交付。五个系统用于GenB中的业务分类和责任归属，不代表五个合并部署单元。继续以`control-system-service`等系统级进程承载多个组件，会造成代码所有权、发布节奏、故障域和验收证据相互耦合。

## 决策

1. 十四个固定核心组件分别拥有一个向GenB注册的公共组件服务。
2. 五个系统仅作为GenB目录分类，不要求存在同名系统级运行服务。
3. 每个公共组件服务独立提供版本化Interface、健康、配置Schema、权限scope、错误语义和验收证据。
4. GenB负责目录、契约、配置、绑定、凭证、组件会话、审计和发现，不作为十四个服务所有高频业务请求的强制数据代理。
5. 智能体先向GenB申请组件会话，再按GenB解析出的绑定直接调用组件服务。
6. 一个组件内部可以依赖其他团队提供的内部服务，但对GenB仍只注册一个公共组件入口。

## 稳定code

为避免迁移已有数据库记录、绑定、权限和测试资产，以当前GenB代码中的code作为稳定真源：

| systemCode | componentCode | 公共服务建议名 |
|---|---|---|
| `CONTROL_SYSTEM` | `PLANNING_REASONING` | `planning-reasoning-service` |
| `CONTROL_SYSTEM` | `SHORT_TERM_MEMORY` | `short-term-memory-service` |
| `CONTROL_SYSTEM` | `LONG_TERM_MEMORY` | `long-term-memory-service` |
| `CONTROL_SYSTEM` | `TOOL_REGISTRY` | `tool-registry-service` |
| `CONTROL_SYSTEM` | `POLICY_GUARDRAILS` | `policy-guardrails-service` |
| `PERCEPTION_SYSTEM` | `DATA_CONNECTORS` | `data-connectors-service` |
| `PERCEPTION_SYSTEM` | `CONTEXT_ENCODER` | `context-encoder-service` |
| `INTERACTION_SYSTEM` | `MULTIMODAL_INTERFACE` | `multimodal-interface-service` |
| `INTERACTION_SYSTEM` | `CONVERSATION_MANAGER` | `conversation-manager-service` |
| `RUNTIME_SYSTEM` | `INFERENCE_ENGINE` | `inference-engine-service` |
| `RUNTIME_SYSTEM` | `ACTION_EXECUTOR` | `action-executor-service` |
| `OPERATIONS_SYSTEM` | `DISTRIBUTED_TRACING` | `distributed-tracing-service` |
| `OPERATIONS_SYSTEM` | `SECURITY_FILTER` | `security-filter-service` |
| `OPERATIONS_SYSTEM` | `FEEDBACK_LOOP` | `feedback-loop-service` |

这些code发布后不得因展示名、团队或实现变化而修改。

## 长期记忆的团队协作

`LONG_TERM_MEMORY`只有一个对GenB公开的服务和一个智能体绑定。内部至少包含两个Module：

- Conversation Memory Module：用户偏好、稳定事实、用户约束、更正、反馈和遗忘。
- Knowledge Base Adapter：对接同事提供的文档、规则、案例、权限、检索和引用能力。

同事的知识库可以独立部署，但它是`long-term-memory-service`的内部依赖，不在GenB中注册成第十五个核心组件。公共长期记忆结果必须标记`sourceType`和`sourceRef`。

## 当前三个组件的收敛顺序

1. `SHORT_TERM_MEMORY`：保留`short-term-memory-service`公共入口，将现有成熟Redis、摘要、动态配置和保护能力收敛到这一服务，随后删除重复入口。
2. `PLANNING_REASONING`：完善需求澄清、Skill生成和运行时计划生命周期。
3. `LONG_TERM_MEMORY`：将Conversation Memory收敛为独立公共服务，并为Knowledge Base定义内部Adapter合同。

其余组件保持`PLANNED`，由对应负责人按统一接入规范交付。

## 后果

- 每个同事可以独立开发、发布和回滚自己负责的组件服务。
- GenB获得统一治理Interface，而不拥有各组件业务Implementation。
- 原`control-system-service`中的长短记忆实现需要迁移后退役，迁移期间不得出现两个生产真源。
- 现有设计文档中“五个系统服务承载十四组件”的描述由本ADR覆盖。
