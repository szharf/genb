# Planning and Reasoning Service

GenB固定核心组件`PLANNING_REASONING`的一期独立逻辑服务，能力归属Control System。它先分析并澄清需求，再生成、校验或修订版本化Skill；不执行Skill、不调用MCP工具、不返回模型原始思维链，也不依赖旧Runtime SDK。

## 当前Interface

| Method | Path | 行为 |
|---|---|---|
| POST | `/api/v1/planning-reasoning/requirements:analyze` | 判断信息是否完整、简单/复杂并给出澄清问题 |
| POST | `/api/v1/planning-reasoning/skills:generate` | 生成简单或复杂Skill v1，要求`Idempotency-Key` |
| POST | `/api/v1/planning-reasoning/skills:validate` | 校验frontmatter、必需章节、MCP声明和原始推理泄露 |
| POST | `/api/v1/planning-reasoning/skills/{skillId}:revise` | 根据失败摘要生成新版本，要求`Idempotency-Key` |
| GET | `/api/v1/planning-reasoning/skills/{skillId}/versions/{version}` | 按租户和智能体读取不可变版本 |
| GET | `/health/live`、`/health/ready` | 存活与存储就绪检查 |

运行时OpenAPI位于`/openapi.json`，可直接用于后续GenB接口契约注册。

## 模板行为

- 简单模板：Purpose、Required Inputs、Workflow、Constraints、Completion Criteria和Exception Handling。
- 复杂模板：在简单结构上增加MCP Tools、Human Approval和Failure Escalation。
- MCP只作为Skill中的声明；真正调用由绑定该Skill的上层智能体负责。
- 异常先按Skill规则处理；超出规则边界时，把失败步骤、错误码、摘要和调整目标交回本服务生成新版本。

## 存储

设置`PLANNING_REASONING_POSTGRES_DSN`时使用PostgreSQL；未设置时使用仅适合单元测试的内存Adapter。迁移脚本只创建：

- `planning_skill_versions`
- `planning_skill_idempotency`

两表有逻辑关系但没有物理外键。版本内容不可覆盖，修订只能追加新版本。

## 本地启动

先在进程环境或Secret管理系统设置`PLANNING_REASONING_POSTGRES_DSN`，再从项目根目录执行：

```powershell
.\scripts\start_planning_reasoning_service.ps1
```

默认监听`127.0.0.1:18712`并使用仅限本地的开发Header身份。正式接入GenB时设置：

```powershell
$env:PLANNING_REASONING_AUTH_MODE='genb'
$env:PLANNING_REASONING_GENB_URL='http://127.0.0.1:8581/api'
$env:PLANNING_REASONING_GENB_INTERNAL_TOKEN='<内部凭证>'
```

正式调用还必须携带智能体服务凭证、GenB Actor Token、`X-Request-Id`，并具有`component:planning-reasoning:invoke` scope。

## 测试

```powershell
& 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe' -m pytest -q
```

设置`PLANNING_REASONING_POSTGRES_DSN`后，测试会额外执行真实PostgreSQL版本、幂等、隔离和无物理外键验收。
