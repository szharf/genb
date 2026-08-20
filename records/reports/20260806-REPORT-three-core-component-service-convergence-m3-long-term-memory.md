# 长期Conversation Memory独立服务M3实施报告

日期：2026-08-06

## 完成内容

- 新建并完成`long-term-memory-service`唯一公共服务：提取、任务查询、跨会话检索、更正、反馈、软删除和遗忘语义。
- 完成GenB双凭证、Actor Token、按操作scope、tenant/user/agent隔离、幂等冲突、敏感候选与置信度过滤。
- 完成Knowledge Base Adapter Protocol、Fake和超时/不可用/无权限/撤权错误边界；混合检索只保留真实Conversation结果并标记降级，不伪造引用。
- 完成In-memory及PostgreSQL Adapter、迁移、事务、租约恢复和本地数据库验收。
- GenB本地长期记忆Implementation和三个现有绑定切至`long-term-memory-service-v1`（18702），旧Implementation禁用。
- 18714使用统一登录原会话完成真实Chrome跨会话验收，旧对话可见，新对话准确召回刚保存的完整偏好。
- Gate D通过后删除Control System四个旧长期HTTP入口、长期Worker启动与长期PostgreSQL ready依赖；运行态旧路径返回404。
- GenB长期调用只允许`LONG_TERM_MEMORY_V1`，不再保留旧Control System长期路径分支。

## 涉及文件

- `long-term-memory-service/`：服务、领域、身份、Adapter、PostgreSQL、OpenAPI、Manifest、测试与验收Runtime。
- `control-system-service/`：删除旧长期公共入口和启动依赖，更新OpenAPI、README和退役合同测试。
- `control-system-test-agent/`：按GenB绑定调用独立长期服务并携带业务`conversationId`。
- `gen-b/gen-b-backend/`：支持`LONG_TERM_MEMORY_V1`登记并移除长期旧路径调用分支。
- `scripts/`：独立服务启动、确定性Runtime、正式验收、绑定切换和本地启动收口。
- `docs/`、`CURRENT_TASKS.md`、计划与记录索引：同步当前唯一真源和Gate证据。

## 验证结果

- 独立长期服务：`31 passed, 1 skipped`；跳过项仅为非数据库运行时未注入DSN的集成测试。
- 本地PostgreSQL专项：`1 passed`。
- Control System：`50 passed, 3 skipped`。
- 18714测试智能体：`63 passed`。
- GenB后端：`HttpCoreComponentInvokerTest`及五个核心组件控制面/详情/Schema相关测试类全部通过。
- 正式本地HTTP/Actor Token验收：`status=SUCCEEDED cross_session=true source=CONVERSATION soft_delete=true actor_token=true`。
- Chrome验收：两个可见会话、完整偏好准确召回、页面显示“验证完成”；没有暴露内部ID、JSON或凭证。
- 运行态Control System：`/health/ready`只报告`shortTermStore=UP`，旧长期路径返回404。
- 本轮只连接本地PostgreSQL、Redis和本地服务；没有操作服务器或服务器数据库。

## 未完成事项

- 真实18704 Runtime调用DeepSeek时仍可能返回`MODEL_STRUCTURED_OUTPUT_INVALID`。Gate D使用本地确定性结构化Runtime验证服务合同和完整链路；真实模型合规性尚未通过，不能把确定性Runtime结果称为真实模型验收。
- Knowledge Base实际业务Adapter仍由负责同事交付，本轮只完成聚合边界和失败语义。
- M1短期记忆收敛按用户要求暂缓；M4 GenB统一接入与M5总验收尚未执行。

## 风险和后续建议

- M4前先为Manifest导入、重复Implementation拒绝和OpenAPI关联建立失败测试，避免通过数据库脚本绕开GenB控制面规则。
- 真实模型问题应单独保留原始错误码与脱敏诊断，不允许在生产启用确定性Runtime或静默降级为规则提取。
- 当前工作树仍包含大量用户和同事修改；本轮未执行破坏性Git操作，也未整理无关差异。
