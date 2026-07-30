# Gen-B Changelog

## 2026-07-30

- 新增不依赖旧SDK的独立短期记忆参考服务，完成四维隔离、跨会话任务恢复、TTL、幂等、脱敏及内存/Redis Adapter。
- GenB固定核心组件和服务实现之间新增接口契约层，支持OpenAPI 3.0/3.1 JSON/YAML上传、粘贴及带默认值的手工录入、发布和查看。
- 管理端新增双语接口契约页签和实现契约版本约束；完成自动化及真实浏览器验收，本轮保持GenB、智能体与新服务不互联。

## 2026-07-23

- 新增`control-system-test-agent`，以同一代码和独立`agentId`/服务凭证运行A/B逻辑智能体。
- 完成GenB组件会话、Control System Short-term Memory、开发PostgreSQL和本地Redis的真实纵向联调。
- 自动验收连续召回、跨会话/A-B隔离、未绑定、停用绑定、错凭证和scope不足；验收Redis键精确清理后残留为0。

## 2026-07-08

- 新增项目级 AI 协作索引体系：`AGENTS.md`、`PROJECT_INDEX.md`、`docs/`、`context/`、`records/`。
- 明确五个核心项目：`bank-agent-cli`、`bank-agent-runtime`、`gen-b-backend`、`gen-b-client`、`gen-b-console`。
- 明确演示期服务器操作约束。
