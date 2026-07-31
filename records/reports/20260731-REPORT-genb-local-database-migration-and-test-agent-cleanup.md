# GenB 本地数据库迁移与服务器测试智能体清理报告

## 1. 目标

- 将 GenB 日常开发数据从服务器 PostgreSQL 迁移到本机 PostgreSQL。
- 本地完成登录、组件服务和测试智能体真实调用验收。
- 验收通过后，清理服务器上只属于本地开发的两个测试智能体及其从属数据。

## 2. 迁移范围

- 来源：服务器 `genb` 数据库。
- 目标：本机 PostgreSQL 的独立数据库 `genb_local`，schema 保持 `bank_agent_db`。
- 保留本机原有 `genb` 数据库，不覆盖、不删除。
- 本机配置和两份本地集成启动脚本均指向 `127.0.0.1:5432/genb_local`；启动脚本显式设置 `GENB_DB_URL`、`GENB_DB_USERNAME`、`GENB_DB_PASSWORD`，不会再因共享配置中的服务器地址误写远程库。

## 3. 备份与恢复

- 服务器迁移前完整备份：`D:\default\Documents\backups\genb-db\20260731\genb-before-local-migration-20260731.dump`
  - SHA256：`9EFCF121BE3E7C324C186C323ADC273C3542DA1A1B7E39EE50179BD01C6609A6`
- 本机旧 `genb` 保护性备份：`D:\default\Documents\backups\genb-db\20260731\genb-local-before-migration-20260731.dump`
  - SHA256：`567910ADFC31F32E52E5D1FC772FA2AE411915C2F612F3AF3F60C03CCEAEE6B9`
- 两个待清理智能体专项 CSV：`D:\default\Documents\backups\genb-db\20260731\remote-test-agent-cleanup\`。
- 完整 dump 已恢复到新建的 `genb_local`；53 张业务表逐表比较，除服务器持续新增的 `system_metrics` 采样外，其余表记录数一致。关键表 `agents`、绑定、凭证、调用、组件目录、实现、配置和用户全部一致。

## 4. 本地验收

- 后端进程已确认实际连接 `127.0.0.1:5432`，不是服务器数据库。
- 规划与推理服务以 PostgreSQL 模式连接 `genb_local` 并返回 `READY`。
- 9100 下的统一登录、智能体列表、短期记忆测试智能体、规划测试智能体和客户核心组件智能体入口均返回 HTTP 200。
- 8581、18704、18705、18711、18712、18713、18714 健康检查全部通过。
- 登录后的智能体接口返回三个测试智能体的正确中文名称。
- 客户核心组件智能体完成真实模型回答，诊断信息解析到 `SHORT_TERM_MEMORY`、`PLANNING_REASONING`、`INFERENCE_ENGINE` 三个启用绑定，并成功提交短期记忆。
- 规划测试智能体真实执行 `ANALYZE`，返回 `READY`。
- GenB 后端全量自动化测试 127 项通过，0 失败、0 错误；三份本地启动脚本 PowerShell 语法检查通过。

## 5. 服务器清理

清理对象仅为：

- `standalone-planning-test-agent`
- `core-component-demo-agent`

事务内删除数量：

| 表/数据 | 数量 |
|---|---:|
| `component_audit_events`（仅对应绑定和凭证） | 12 |
| `alert_records` | 2 |
| `agent_invocations` | 9 |
| `operation_logs` | 5 |
| `service_credentials` | 2 |
| `agent_component_bindings` | 4 |
| `agents` | 2 |

提交后遍历服务器所有包含 `agent_id` 的表，相关记录为 0。共享数据保持不变：14 个组件目录、6 个实现、8 个配置版本仍在服务器。

## 6. 当前访问地址

- 统一登录：`http://localhost:9100/portal/login`
- 短期记忆测试智能体：`http://localhost:9100/agents/standalone-memory-test-agent/chat`
- 规划与推理测试智能体：`http://localhost:9100/agents/standalone-planning-test-agent/planning`
- 客户核心组件智能体：`http://localhost:9100/core-agent/`

9100 是统一登录和同源入口；三个智能体自身仍分别运行在独立服务端口，9100 只做前端入口和反向代理。
