# 规划与推理引擎独立服务操作手册

> 日期：2026-07-30
> 本地地址：`http://127.0.0.1:18712`
> 固定组件编码：`PLANNING_REASONING`

## 1. 这个服务做什么

规划与推理引擎把业务描述转换为可复用Skill。它只做四件事：澄清、生成、校验、修订。它不运行Skill，也不直接调用HTTP、SDK或MCP工具。

简单需求使用标准模板。复杂、多工具或高风险需求使用复杂模板，其中可以写明MCP服务名、工具名、人工确认点和失败升级规则。真正执行时，上层智能体读取Skill并调用已经授权的工具。

## 2. 启动和检查

1. 在PowerShell中通过安全环境变量设置`PLANNING_REASONING_POSTGRES_DSN`，不要写入源码或文档。
2. 进入`D:\code\opencode\genb`。
3. 执行`.\scripts\start_planning_reasoning_service.ps1`。
4. 浏览器打开`http://127.0.0.1:18712/health/ready`。
5. 应看到`status=UP`、`authoring=TEMPLATE`、`store=POSTGRESQL`。
6. 打开`http://127.0.0.1:18712/docs`可以逐接口测试。

## 3. 第一步：分析需求

1. 在Swagger点击`POST /api/v1/planning-reasoning/requirements:analyze`。
2. 点击“Try it out”。
3. Headers输入开发测试身份：`X-Tenant-Id=tenant-demo`、`X-Agent-Id=agent-demo`、`X-User-Id=user-demo`。
4. Request body先只输入：

```json
{"goal":"生成一个授信审查Skill"}
```

5. 点击“Execute”。
6. 返回`NEEDS_CLARIFICATION`，并要求补充`expectedInputs`、`expectedOutputs`、`constraints`。这一步证明服务不会在需求不清楚时猜测完整流程。

## 4. 生成简单Skill

1. 点击`POST /api/v1/planning-reasoning/skills:generate`和“Try it out”。
2. 保持三个身份Header与上一步一致。
3. `Idempotency-Key`输入唯一值，例如`demo-simple-20260730-001`。
4. Body输入：

```json
{
  "name":"授信材料检查",
  "description":"检查申请材料是否齐全并输出缺失清单",
  "requirements":{
    "goal":"检查授信申请材料",
    "expectedInputs":["授信申请表","材料清单"],
    "expectedOutputs":["缺失材料清单"],
    "constraints":["不得修改原始材料"]
  }
}
```

5. 点击“Execute”。预期HTTP 201、`complexity=SIMPLE`、`version=1`、`validation.valid=true`。
6. `skillMarkdown`应包含Purpose、Required Inputs、Workflow、Constraints、Completion Criteria和Exception Handling，不包含MCP章节。
7. 使用完全相同的幂等键和Body再次执行，应返回同一个`skillId`；同一幂等键换Body应返回409。

## 5. 生成复杂MCP Skill

1. 仍使用生成接口，换一个幂等键。
2. 把`riskLevel`设为`HIGH`，在`toolReferences`中填写MCP的`server`、`tool`和`purpose`。
3. 执行后应看到`complexity=COMPLEX`。
4. `skillMarkdown`应包含MCP Tools、Human Approval、Failure Escalation。
5. MCP工具显示为`server.tool`，但此时没有发生真实工具调用。

## 6. 校验和修订

1. 把生成的Markdown提交到`POST /skills:validate`，正常结果为`valid=true`。
2. 删除frontmatter或必需章节再次校验，结果为`valid=false`并列出具体问题。
3. 模拟执行失败时，调用`POST /skills/{skillId}:revise`。
4. `baseVersion`输入当前版本，`failure`填写失败步骤、稳定错误码和脱敏摘要，`adjustmentGoal`写期望的降级或调整目标。
5. 返回新版本，例如v2；再调用`GET /skills/{skillId}/versions/1`，v1内容仍保持不变。

## 7. 后续GenB联通

本轮服务独立验收后，下一任务需要在GenB完成：发布OpenAPI契约、注册`18712` Implementation、发布配置、绑定测试智能体、增加管理员服务直测和智能体绑定测试。正式模式下开发Header失效，必须使用服务凭证和GenB Actor Token。
