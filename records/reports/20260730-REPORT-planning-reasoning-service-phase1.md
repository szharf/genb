# 规划与推理引擎独立服务一期实施报告

> 日期：2026-07-30
> 固定组件：`PLANNING_REASONING`
> 本地服务：`http://127.0.0.1:18712`

## 1. 交付结果

已新建`planning-reasoning-service`，作为Control System下规划与推理引擎核心组件的独立逻辑服务。服务通过一个HTTP Interface隐藏需求判断、模板选择、Markdown渲染、校验、版本和身份复杂度。

当前实现先澄清需求，再按规则生成简单或复杂Skill。复杂模板支持MCP工具声明、人工确认和失败升级；服务本身不执行Skill和工具。失败事件可以生成新版本，旧版本不可覆盖且可按版本回读。

## 2. Interface

- `requirements:analyze`：规范化目标、判断复杂度并返回缺失字段问题。
- `skills:generate`：生成Skill v1并保证幂等。
- `skills:validate`：校验frontmatter、必需章节、MCP声明和原始推理泄露。
- `skills/{skillId}:revise`：用脱敏失败摘要生成下一版本。
- `skills/{skillId}/versions/{version}`：按已验证租户和智能体读取指定版本。
- `/openapi.json`：OpenAPI 3.1运行契约。

## 3. 数据和安全

远程开发PostgreSQL已通过可重复迁移创建：

- `planning_skill_versions`
- `planning_skill_idempotency`

两张表没有物理外键。Skill按`tenantId + agentId`隔离，版本内容只追加不覆盖；生成和修订都使用请求指纹防止幂等键冲突。

正式身份模式验证GenB RS256 Actor Token、`PLANNING_REASONING`组件、`component:planning-reasoning:invoke` scope和智能体服务凭证。自报身份Header只在明确的本地开发模式有效。生成结果和日志不包含服务凭证、Token或模型原始思维链。

## 4. 模板策略

- 简单：六个基础章节，适合输入、处理、输出边界清晰的单流程Skill。
- 复杂：增加MCP Tools、Human Approval、Failure Escalation，适合多工具、高风险和跨系统流程。
- 异常处理：Skill规则内由上层智能体处理；超过规则边界后提交失败步骤、错误码、摘要和调整目标，生成新版本。

当前`authoring=TEMPLATE`，采用确定性模板保证离线可验收。模型增强Adapter尚未接入；后续应通过Runtime System Inference Engine完成更自然的澄清和业务步骤生成，同时保留现有校验与版本Interface。

## 5. 验收证据

- 单元/HTTP/身份/契约测试及PostgreSQL集成测试：12项通过。
- 远程PostgreSQL Adapter：生成幂等、v1/v2、租户智能体隔离和无物理外键通过。
- 真实HTTP：澄清、复杂模板、MCP声明、校验、修订v2和v1不可变全部通过。
- 就绪检查：`status=UP`、`authoring=TEMPLATE`、`store=POSTGRESQL`。

## 6. 后续工作

1. 把`/openapi.json`注册为GenB `PLANNING_REASONING`接口契约。
2. 注册`18712` Implementation、发布配置并绑定专用测试智能体。
3. 扩展GenB管理员服务直测和智能体绑定测试适配器。
4. 接入Runtime System模型生成Adapter，增加模板目录治理和更多业务模板。
