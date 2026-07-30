# 规划与推理引擎独立服务一期任务计划

> 日期：2026-07-30
> 固定组件编码：`PLANNING_REASONING`
> 能力归属：Control System

## 1. 已确认需求

1. 五大系统是能力分类，14个核心组件是固定逻辑服务；规划与推理引擎归属Control System。
2. 规划引擎生成和调整Skill，不负责执行Skill、模型工具调用或业务动作。
3. 简单需求直接生成标准Skill；复杂需求选择结构化模板，可在Skill中声明MCP工具调用方法。
4. 生成前必须检查需求完整性，缺少目标、输入、输出或约束时先提出澄清问题。
5. 已有固定Skill或工作流的垂直智能体可以不绑定规划引擎。
6. 异常先由Skill中声明的规则处理；超出规则边界时，允许调用规划引擎生成新版本或临时调整方案。
7. 只输出可审计的决策摘要，不输出或保存模型原始思维链。

## 2. 一期公开Interface

| Method | Path | 责任 |
|---|---|---|
| POST | `/api/v1/planning-reasoning/requirements:analyze` | 规范化需求、判断复杂度、返回澄清问题 |
| POST | `/api/v1/planning-reasoning/skills:generate` | 基于已澄清需求生成Skill v1 |
| POST | `/api/v1/planning-reasoning/skills:validate` | 校验Skill frontmatter、必需章节和MCP声明 |
| POST | `/api/v1/planning-reasoning/skills/{skillId}:revise` | 根据失败事件生成新版本，不覆盖旧版本 |
| GET | `/api/v1/planning-reasoning/skills/{skillId}/versions/{version}` | 查询指定Skill版本 |
| GET | `/health/live`、`/health/ready` | 存活和就绪检查 |

## 3. Module与Seam

- HTTP Interface：唯一外部Seam，调用方只学习需求、Skill和版本模型。
- Requirement Analyzer Module：隐藏字段完整性、复杂度和高风险识别规则。
- Skill Authoring Module：隐藏模板选择、名称规范化、MCP声明、异常规则和Markdown渲染。
- Skill Validation Module：通过同一公开校验Interface验证生成结果和外部Skill。
- Version Repository Seam：提供内存测试Adapter和PostgreSQL运行Adapter，保持旧版本不可变。
- Identity Module：复用GenB服务凭证、RS256 Actor Token、组件编码和scope门禁。

## 4. TDD纵向切片

| 顺序 | 可观察行为 | 状态 | 验证 |
|---:|---|---|---|
| 1 | 缺少关键信息时返回澄清问题 | 已完成 | HTTP RED→GREEN |
| 2 | 简单需求生成可校验标准Skill | 已完成 | HTTP RED→GREEN |
| 3 | 复杂需求生成MCP/人工确认/异常规则模板 | 已完成 | HTTP RED→GREEN |
| 4 | 非法Skill被校验Interface拒绝 | 已完成 | HTTP RED→GREEN |
| 5 | 失败事件修订产生新版本且旧版本不变 | 已完成 | HTTP RED→GREEN |
| 6 | GenB身份和scope fail-closed | 已完成 | 身份集成测试 |
| 7 | PostgreSQL、OpenAPI、启动和操作文档 | 已完成 | 远程库、契约测试与本地HTTP验收 |
| 8 | 全量审查、报告、索引和提交 | 已完成 | pytest、diff和秘密扫描 |

## 5. 非目标

- 不执行生成的Skill或MCP工具。
- 不在一期提供通用工作流引擎、动作补偿器或工具注册表。
- 不保存模型原始思维链。
- 不在本轮注册到GenB、不绑定智能体、不修改管理端页面。
- 不在本轮接入模型生成Adapter；当前使用确定性模板，模型增强在服务独立验收后迭代。

## 6. 数据表

- `planning_skill_versions`：按`skillId + version`保存不可变Skill版本。
- `planning_skill_idempotency`：按`tenantId + agentId + idempotencyKey`保存请求指纹和结果版本。
- 两表仅在设计上存在逻辑关系，实际建表没有物理外键。
