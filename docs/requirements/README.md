# 需求与 PRD 文档

本目录用于存放 Gen-B 的 PRD、业务规则、流程说明、需求变更记录和功能验收标准。

## 什么时候写需求文档

以下情况必须写：

- 新增页面或主流程。
- 修改登录、权限、审批、授权、智能体状态等核心业务规则。
- 新增数据库表、字段或接口契约。
- 影响客户端和管理端共同能力。
- 涉及部署、数据迁移或角色权限。

## 命名规范

| 类型 | 命名 |
|---|---|
| PRD | `YYYYMMDD-PRD-主题.md` |
| 需求变更 | `YYYYMMDD-REQ-主题.md` |
| 流程说明 | `YYYYMMDD-FLOW-主题.md` |
| 验收清单 | `YYYYMMDD-ACCEPTANCE-主题.md` |

## 标准结构

```md
# 标题

日期：
状态：草稿 / 已确认 / 已实现 / 已下线

## 背景

## 目标

## 不做什么

## 用户角色

## 业务流程

## 页面范围

## 接口范围

## 数据模型

## 权限规则

## 状态规则

## 异常场景

## 成功标准

## 验证方式

## 待确认问题
```

## Gen-B 当前已知需求域

| 需求域 | 说明 | 涉及项目 |
|---|---|---|
| 统一登录 | 一个登录页，根据角色进入客户端或管理端。 | `gen-b-backend`、`gen-b-client`、`gen-b-console` |
| 用户角色权限 | 用户、角色、权限码、管理端准入、客户端可见性。 | `gen-b-backend` |
| 我的智能体 | 展示已授权且具备访问条件的智能体。 | `gen-b-client`、`gen-b-backend` |
| 智能体市场 | 展示可浏览、可申请、审批中、已拒绝的智能体。 | `gen-b-client`、`gen-b-backend` |
| 我的申请 | 展示当前用户申请记录和审核结果。 | `gen-b-client`、`gen-b-backend` |
| 权限审批 | 管理员审核业务用户智能体使用申请。 | `gen-b-client`、`gen-b-backend` |
| 智能体状态 | Python 运行状态、Docker 镜像状态、访问端口、发布状态。 | `gen-b-backend`、`gen-b-console`、`gen-b-client` |
| 智能体生成和运行 | CLI 生成智能体，Runtime 提供运行底座。 | `bank-agent-cli`、`bank-agent-runtime` |

## 已有需求文档

- `CORE_COMPONENT_STRUCTURE_PLANNING_SHORT_TERM_CONFIRMATION.md`：五大系统/14组件总体结构、规划与推理引擎、短期记忆/工作台的功能边界和一期效果待确认清单。
- `CLIENT_I18N_COPY_MAP.md`：客户端英文版文案对照。
