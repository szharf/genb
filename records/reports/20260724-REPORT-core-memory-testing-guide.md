# 核心记忆测试台与测试智能体操作手册报告

## 1. 背景

长短期记忆纵向切片已经具备页面测试台和测试智能体，但页面字段、凭证来源、测试顺序、结果含义，以及智能体列表中 `DRAFT / STOPPED` 的含义容易混淆，需要形成面向非开发人员的可执行说明。

## 2. 目标

交付一份逐点击、逐输入的正式测试手册，并提供浏览器教学页和现场快速参考，使管理员能够独立验证短期记忆、长期记忆、Session 隔离、A/B 智能体隔离和身份失败矩阵。

## 3. 范围

- GenB 独立测试台当前真实页面行为。
- GenB、Control、Runtime、Redis、PostgreSQL 启动与健康检查。
- 服务凭证的获取、安全使用和吊销。
- `memory-test-a/b/unbound` 的当前运行形态。
- 短期与长期 CLI acceptance。
- 测试证据、数据影响、清理和排障。

不包含把测试智能体改造成常驻 HTTP 服务，也不把 Fake Provider 链路验收描述为真实模型质量验收。

## 4. 完成标准

- 页面长短期测试覆盖一期主要正向、隔离和错凭证场景。
- 每个字段都有来源、含义和填写原因。
- 说明测试智能体为什么不需要在列表中启动。
- 提供可直接运行的 PowerShell 和验收脚本步骤。
- 文档加入项目、文档和历史记录索引。

## 5. 实施内容

- 新增 `docs/operation/CORE_MEMORY_TESTBENCH_AND_TEST_AGENT_GUIDE.md`。
- 新增 `docs/training/core-memory-testing/` 教学工作区，包括 Mission、Resources、Notes、共享样式、第一课和快速参考。
- 明确 A/B 当前只有逻辑身份、绑定和 CLI 夹具，没有 host、port、workDirectory、startCommand 或容器信息。
- 明确页面测试不依赖 A/B 常驻进程；CLI 每次执行时创建调用方，完成后正常退出。
- 明确若未来要求显示 `RUNNING`，必须补常驻 HTTP 服务、健康接口和真实部署配置，不能直接修改数据库状态。

## 6. 当前进度

全部完成。任务看板已同步关闭本项文档任务。

## 7. 验收

- 手册覆盖短期首次/连续/Session 隔离/A-B 隔离/错凭证。
- 手册覆盖长期提取/写入/召回/跨 Session，以及脚本严格隔离、敏感拒绝和软删除。
- 教学页与快速参考均复用共享样式，并链接正式手册。
- 文档中的凭证均为占位符，不记录管理员密码、服务凭证、Token 或 Redis 密码明文。
- 索引已更新：`PROJECT_INDEX.md`、`docs/INDEX.md`、`docs/operation/README.md`、`records/RECORDS_INDEX.md`。

## 8. 风险与后续

- 当前凭证签发仍需要管理员 API 或 provisioning 脚本，后续可以开发可审计的一次性签发页面。
- 当前 Runtime 为 Fake 结构化结果，必须在真实 Provider 可用后另做质量、成本、配额和合规验收。
- 若项目决定演示“智能体在线运行”，需另立任务把 CLI 包装为常驻服务，并设计启动、停止、健康和日志能力。
