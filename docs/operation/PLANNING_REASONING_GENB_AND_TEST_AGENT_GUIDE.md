# 规划与推理引擎 GenB 测试台与测试智能体操作手册

更新时间：2026-07-30

## 1. 这套功能现在由什么组成

| 部分 | 地址/标识 | 作用 |
|---|---|---|
| GenB 用户入口 | `http://localhost:9100` | 登录、管理端入口、我的智能体和内置测试页面 |
| GenB 后端 | `http://127.0.0.1:8581/api` | 管理契约、实现、配置、绑定、凭证并签发 Actor Token |
| 规划与推理服务 | `http://127.0.0.1:18712` | 澄清需求、生成Skill、校验Skill、按失败事件修订Skill |
| 专用测试智能体 | `standalone-planning-test-agent`，端口`18713` | 向GenB申请组件会话，再调用GenB返回的规划服务 |
| 固定核心组件 | `PLANNING_REASONING` | GenB中固定的14个组件之一，归属Control System |

调用链是：

```text
页面中的登录用户Token
→ 专用测试智能体（服务端持有自己的长期服务凭证）
→ GenB校验用户、智能体凭证和启用绑定
→ GenB返回实现地址、配置快照和5分钟Actor Token
→ 测试智能体调用规划与推理服务
→ 规划服务再次校验Actor Token和服务凭证
→ 返回澄清问题、Skill或校验结果
```

规划服务只生成、校验和修订Skill，不执行Skill，也不实际调用Skill中声明的MCP或HTTP工具。

## 2. 首次或重启后的启动方法

打开PowerShell，执行：

```powershell
cd D:\code\opencode\genb
.\scripts\start_planning_integration_local.ps1 -Password '<管理员密码>' -RedisPassword '<Redis密码>'
```

脚本会启动或重启`8581`、`18705`、`18712`和`18713`，并幂等检查规划契约、实现、配置和绑定。长期服务凭证及内部令牌使用当前Windows用户的DPAPI加密后存入`.local-secrets`，不会以明文进入Git。

正常情况下不要加`-RotateAgentCredential`。只有确认凭证泄漏或需要主动轮换时才执行：

```powershell
.\scripts\start_planning_integration_local.ps1 -Password '<管理员密码>' -RedisPassword '<Redis密码>' -RotateAgentCredential
```

轮换会立即吊销旧凭证，并用新凭证重启测试智能体。

## 3. 管理员服务直测：不经过智能体

这个模式用于回答“规划服务本身是否可用”。它不要求智能体、绑定或服务凭证，但GenB仍会签发仅供管理员测试的短时Actor Token并写审计。

1. 浏览器打开`http://localhost:9100/portal/login`。
2. 输入管理员用户名和密码，点击“登录”。
3. 点击右上角“进入管理端”。
4. 左侧展开“智能体中心”，点击“核心组件”。
5. 在卡片中找到“规划与推理引擎”，点击卡片或“详情”。
6. 点击顶部页签“独立测试台”。
7. 点击内层页签“管理员服务直测”。
8. “服务实现”选择`planning-reasoning-service-v1 · PLANNING_REASONING_V1`。
9. “已发布配置”选择`default · v1`。
10. “测试会话ID”保留自动生成值，或输入`planning-direct-demo-1`。只允许字母、数字、点、下划线、冒号和连字符。
11. “规划操作”选择`ANALYZE`。页面会自动填入：

```json
{
  "goal": "生成一个授信材料检查Skill"
}
```

12. 点击“调用规划与推理服务”。
13. 结果应显示`SERVICE_DIRECT`、实际实现`planning-reasoning-service-v1`和`NEEDS_CLARIFICATION`。
14. `questions`中的三项分别表示还需补充输入、输出和约束；这证明规划引擎没有在需求不完整时伪造完整Skill。

## 4. 管理端智能体绑定测试：经过凭证与绑定

这个模式用于回答“某个智能体是否确实获准调用此组件”。

1. 保持在“独立测试台”，点击“智能体绑定测试”。
2. “绑定智能体”选择“规划与推理核心组件测试智能体（`standalone-planning-test-agent`）”。
3. 页面会从当前管理员浏览器中回填该智能体的服务凭证；如果没有，点击“生成服务凭证”。
4. 生成凭证会吊销该智能体的旧凭证，因此运行中的测试智能体也必须同步更新。正常重启应使用启动脚本读取DPAPI凭证，不要反复生成。
5. “测试会话ID”输入`planning-binding-demo-1`。
6. “规划操作”先选择`ANALYZE`，保留示例JSON。
7. 点击“调用规划与推理服务”。
8. 结果应显示`AGENT_BINDING`和`NEEDS_CLARIFICATION`。

这个成功结果同时证明：用户有权使用智能体、服务凭证属于该智能体、规划绑定处于启用状态、实现与配置有效、规划服务接受GenB签发的身份。

## 5. 客户端专用测试智能体

1. 打开`http://localhost:9100/my-agents`。
2. 找到“规划与推理核心组件测试智能体”。
3. 点击“使用”或“打开”，进入`/agents/standalone-planning-test-agent/planning`。
4. 页面中的服务凭证不可见；凭证只存在于`18713`智能体进程中。
5. “会话ID”保留自动值，或输入`planning-client-demo-1`。
6. 按下面四组操作依次测试。

### 5.1 ANALYZE：先澄清需求

- “操作”选择`ANALYZE`。
- 输入：

```json
{
  "goal": "生成一个授信材料检查Skill"
}
```

- 点击“真实调用”。
- 预期：`status`为`NEEDS_CLARIFICATION`，并返回`expectedInputs`、`expectedOutputs`、`constraints`三个问题。

### 5.2 GENERATE：生成完整Skill v1

- “操作”选择`GENERATE`，页面会自动装入完整示例。
- 可直接保留示例，点击“真实调用”。
- 预期：返回`skillId`、`version: 1`、`skillMarkdown`和`validation.valid: true`。
- 复制并保存结果中的`skillId`；后面的修订需要使用它。

如需测试复杂Skill，把`riskLevel`改为`HIGH`，并在`toolReferences`中填写：

```json
[
  {
    "protocol": "MCP",
    "server": "enterprise-registry",
    "tool": "query-company",
    "purpose": "查询企业登记信息"
  }
]
```

预期生成内容包含`MCP Tools`、`Human Approval`和`Failure Escalation`章节，但不会真正调用这个MCP工具。

### 5.3 VALIDATE：校验Skill文本

- “操作”选择`VALIDATE`。
- 把上一步返回的完整`skillMarkdown`粘贴到`skillMarkdown`字符串中；JSON中的换行必须使用`\n`转义。
- 简单Skill使用`"requireMcp": false`，要求必须包含MCP声明时改为`true`。
- 点击“真实调用”。
- 预期：合法Skill返回`valid: true`；缺少必要章节时返回`valid: false`及`issues`。

### 5.4 REVISE：根据失败生成v2

- “操作”选择`REVISE`。
- 把`skillId`替换为GENERATE返回值，`baseVersion`第一次填写`1`。
- 示例：

```json
{
  "skillId": "skill_替换为真实ID",
  "baseVersion": 1,
  "failure": {
    "failedStep": "检查材料",
    "errorCode": "INPUT_MISSING",
    "summary": "缺少必要材料"
  },
  "adjustmentGoal": "增加缺失材料提示并转人工补充"
}
```

- 点击“真实调用”。
- 预期：返回相同`skillId`、`version: 2`和新的Skill正文；v1仍可查询，未被覆盖。

## 6. 四个操作分别代表什么

| 操作 | 何时用 | 会写数据库吗 | 返回重点 |
|---|---|---|---|
| `ANALYZE` | 需求还没讲清楚时 | 否 | 是否可生成、复杂度、澄清问题 |
| `GENERATE` | 输入、输出、约束已明确时 | 是 | Skill ID、v1正文、校验结果 |
| `VALIDATE` | 检查外部或人工编辑的Skill | 否 | `valid`及问题列表 |
| `REVISE` | Skill执行失败后需要调整规则时 | 是 | 同一Skill的新版本，旧版本不变 |

## 7. 常见失败如何判断

| 页面现象 | 含义 | 处理 |
|---|---|---|
| 没有可选服务实现 | 实现未注册或已停用 | 在“服务实现”页签启用`planning-reasoning-service-v1` |
| 没有可选配置 | 没有已发布配置 | 在“配置版本”页签发布`default`配置 |
| 没有可选智能体 | 绑定不存在或已停用 | 在“智能体绑定”页签创建/启用绑定 |
| 服务凭证无效 | 凭证已被轮换、吊销或不属于当前智能体 | 用启动脚本加`-RotateAgentCredential`重新同步 |
| 返回澄清问题 | 正常业务结果，不是错误 | 回答问题后把完整内容放入GENERATE请求 |
| GENERATE返回409 | 需求仍不完整或幂等请求冲突 | 先ANALYZE并补齐字段，再重新生成 |
| REVISE返回404 | Skill ID或版本不属于当前租户/智能体 | 使用同一测试智能体生成的真实Skill ID |
| REVISE返回409 | `baseVersion`不是最新版本 | 查询或使用最新版本号后再修订 |

## 8. 当前本地注册结果

- 发布契约：ID `2`，版本`1.0.0`，解析出7个HTTP操作。
- 服务实现：ID `5`，`planning-reasoning-service-v1`，适配器`PLANNING_REASONING_V1`。
- 发布配置：ID `7`，`default v1`。
- 智能体绑定：ID `7`，`standalone-planning-test-agent`，状态`ENABLED`。
- 实际表不创建物理外键；组件、实现、配置和绑定关系由业务字段及服务校验维护。
