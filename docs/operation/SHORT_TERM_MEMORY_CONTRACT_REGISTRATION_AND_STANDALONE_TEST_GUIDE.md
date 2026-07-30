# 短期记忆接口契约注册与独立服务测试逐点击手册

> 版本：1.0
> 日期：2026-07-30
> 适用对象：第一次使用GenB的管理员、产品经理、测试人员
> GenB入口：`http://localhost:9100/genb/core-components`
> 短期记忆Swagger：`http://127.0.0.1:18705/docs`

## 1. 先理解本次要做什么

本次有两个彼此独立的对象：

1. **GenB核心组件管理模块**：保存“短期记忆组件应该提供哪些接口”的契约。
2. **短期记忆组件服务**：真正保存、读取、恢复和删除短期记忆。

本轮只证明两边分别可用，不把两边连起来。因此完成本手册后应看到：

- GenB中存在一份包含5个接口的已发布契约。
- 短期记忆服务可以在自己的Swagger中独立完成保存与恢复。
- GenB中没有新增短期记忆服务实现、没有新增智能体绑定、没有向短期记忆服务发送请求。

这不是漏做，而是本轮约定的隔离验收边界。

## 2. 五个容易混淆的名词

| 名词 | 它代表什么 | 本轮是否操作 |
|---|---|---|
| 核心组件 | 固定14项能力中的一项，例如短期记忆 | 查看 |
| 接口契约 | 该逻辑组件服务提供的全部方法、路径、参数和响应 | 创建、查看、发布 |
| 服务实现 | 某个团队部署出来的真实服务地址 | 只查看选择规则，不保存 |
| 配置版本 | 服务实现的非敏感运行参数 | 不创建 |
| 智能体绑定 | 允许指定智能体使用某个实现和配置 | 不创建 |

正确顺序是：

```text
固定组件 → 接口契约草稿 → 检查接口 → 发布契约
         → 服务实现 → 配置发布 → 智能体绑定 → 运行调用
```

本轮在“发布契约”处停止。

## 3. 开始前检查

### 3.1 检查GenB页面

1. 打开浏览器。
2. 地址栏输入 `http://localhost:9100/genb/core-components`。
3. 按Enter。
4. 如果跳到登录页，使用具有管理员权限的账号登录。
5. 左侧应看到“智能体中心”，其下有“智能体列表”和“核心组件”。
6. 页面应显示“5个系统 · 14个组件”。

如果接口返回403，不要关闭后端鉴权。应重新登录或为当前角色补充 `component.read`、`component.configure` 权限。

### 3.2 准备样例文件

样例文件位置：

```text
D:\code\opencode\genb\docs\samples\short-term-memory-contract-v1.yaml
```

该文件包含同一个短期记忆逻辑服务的5个接口，不是5个组件，也不是5个独立项目。

## 4. 推荐操作：上传YAML注册契约

### 4.1 进入短期记忆详情

1. 左侧点击“智能体中心”。
2. 点击其下的“核心组件”。
3. 在“策略控制系统”区域找到“短期记忆/工作台”。
4. 点击整张“短期记忆/工作台”卡片。
5. 页面标题应显示“短期记忆/工作台”和编码 `SHORT_TERM_MEMORY`。
6. 默认选中的第一个页签应为“接口契约”。

### 4.2 打开新建窗口

1. 在“接口契约”页签右上角点击“新建契约”。
2. 弹窗标题应为“新建接口契约草稿”。
3. 先阅读蓝色提示：这里只登记接口，不连接或调用真实服务。

### 4.3 填写基础字段

逐项填写：

| 页面字段 | 输入值 | 为什么这样填 |
|---|---|---|
| 契约版本 | `1.0.0` | 标识首个稳定接口版本；同一组件不能重复 |
| 变更说明 | `短期记忆独立服务首版接口契约` | 让审计和后续升级能说明变化原因 |
| 录入方式 | 点击“上传文件” | 已有标准OpenAPI文件时最不容易抄错 |

### 4.4 选择文件

1. 点击“选择 JSON/YAML 文件”。
2. 文件选择窗口中进入 `D:\code\opencode\genb\docs\samples`。
3. 选中 `short-term-memory-contract-v1.yaml`。
4. 点击系统文件窗口的“打开”。
5. 页面“文档格式”应自动切换为“OpenAPI YAML”。
6. 文件名应显示为 `short-term-memory-contract-v1.yaml`。
7. 下方“文件内容预览”应有内容且只读。

“只读取文件内容，不会上传到组件服务”的含义是：浏览器把文本交给GenB管理后端保存为契约；此时短期记忆服务仍不会收到任何请求。

### 4.5 保存草稿

1. 点击右下角“保存草稿”。
2. 弹窗关闭。
3. 页面右下角应提示“接口契约草稿已创建”。
4. 列表应新增一行：
   - 契约版本：`1.0.0`
   - 协议：`HTTP`
   - 录入方式：`DOCUMENT_UPLOAD`
   - 来源：`short-term-memory-contract-v1.yaml`
   - 接口数：`5`
   - 状态：`草稿`

如果接口数不是5，先不要发布。点击“查看接口”检查文档内容。

## 5. 查看5个接口

1. 在刚创建的契约行点击“查看接口”。
2. 右侧抽屉应显示版本、协议、来源、文件名和SHA-256校验值。
3. 抽屉中应有以下5项：
   - `PUT /api/v1/short-term-memory/tasks/{taskId}` · `saveTaskWorkbench`
   - `GET /api/v1/short-term-memory/tasks/{taskId}` · `getTaskWorkbench`
   - `DELETE /api/v1/short-term-memory/tasks/{taskId}` · `deleteTaskWorkbench`
   - `POST /api/v1/short-term-memory/turns:commit` · `commitShortTermTurn`
   - `POST /api/v1/short-term-memory/context:prepare` · `prepareShortTermContext`
4. 点击任意一项，展开后查看“权限、参数、请求体、响应”。
5. 点击抽屉右上角“×”关闭。

`operationId`是程序稳定识别接口的名称。方法或路径以后可以按版本演进，但同一契约内的 `operationId` 不能重复。

## 6. 发布契约

1. 确认接口数为5、每个接口名称正确。
2. 点击该草稿行右侧“发布”。
3. 在“确认发布”弹窗再次核对版本。
4. 点击“OK”或“确定”。
5. 状态应从“草稿”变成“已发布”。
6. “发布”按钮应消失，只保留“查看接口”。

发布意味着该接口定义成为实现可以声明支持的稳定版本。已发布内容不直接修改；变化时新建 `1.1.0` 或 `2.0.0`。

## 7. 验证服务实现只能选择已发布版本，但不要连接

1. 点击“服务实现”页签。
2. 点击“注册实现”。
3. 找到“接口版本”。
4. 它现在应是下拉框，不是随意输入框。
5. 下拉框应显示 `1.0.0 (5 个接口)`。
6. 不填写“实现编码、负责人、服务地址、健康检查”。
7. 点击右上角“×”或左下角“取消”。

不要点击“注册实现”。这样便证明约束已经生效，同时保持本轮“不连通”。

## 8. 另外两种录入方式

### 8.1 粘贴文档

适合接口开发人员从Swagger或代码生成器复制OpenAPI正文：

1. 点击“接口契约”→“新建契约”。
2. 契约版本输入一个未使用版本，例如 `1.0.1-draft`。
3. 变更说明输入 `验证JSON粘贴录入`。
4. 点击“粘贴文档”。
5. 选择“OpenAPI JSON”或“OpenAPI YAML”。
6. 把完整文档粘贴到“OpenAPI文档内容”。
7. 点击“保存草稿”。

JSON在浏览器中先做格式检查；JSON和YAML最终都由后端检查OpenAPI版本、`info`、`paths`、`operationId`和`responses`。

### 8.2 手工填写

适合还没有OpenAPI文件、只有少量接口的组件负责人：

1. 点击“接口契约”→“新建契约”。
2. 保持“手工填写”。
3. 页面自动给出第一条接口默认值：
   - 请求方式：`POST`
   - 路径：`/api/v1/short-term-memory`
   - operationId：`invokeShortTermMemory`
   - 请求、响应Schema：空对象Schema
4. 按真实接口修改“请求方式、请求路径、operationId、接口说明”。
5. 请求Schema和响应Schema必须是JSON对象。
6. 如接口需要权限，在“所需权限标识”中用英文逗号分隔，例如 `memory.read,memory.write`。
7. 一个组件服务有多个接口时，点击“新增接口”，继续填写第2、3条。
8. 填错的附加接口可点击其右上角“删除”；至少保留一条。
9. 点击“保存草稿”。

手工模式保存时，GenB后端会把这些字段统一生成OpenAPI 3.1 JSON，因此后续查看、发布和版本约束与上传模式完全一致。

## 9. 独立启动短期记忆服务

打开一个新的PowerShell窗口，执行：

```powershell
Set-Location D:\code\opencode\genb\short-term-memory-service
$env:SHORT_TERM_MEMORY_STORE='in_memory'
& 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe' -m uvicorn short_term_memory.main:app --app-dir src --host 127.0.0.1 --port 18705
```

看到Uvicorn启动完成后不要关闭该窗口。浏览器打开 `http://127.0.0.1:18705/docs`。

生产式Redis模式把 `SHORT_TERM_MEMORY_STORE` 改成 `redis`，并通过环境变量提供主机、端口、DB和密码。密码不能填写到GenB普通配置、接口正文、截图或文档中。

## 10. 在Swagger逐项测试短期记忆

以下所有业务接口的三个身份Header固定使用：

| Header | 输入值 |
|---|---|
| X-Tenant-Id | `tenant-demo` |
| X-Agent-Id | `memory-component-test-agent` |
| X-User-Id | `user-demo-a` |

### 10.1 保存任务工作台

1. 展开 `PUT /api/v1/short-term-memory/tasks/{task_id}`。
2. 点击“Try it out”。
3. `task_id` 输入 `credit-review-001`。
4. 填写上表三个Header。
5. Request body替换为：

```json
{
  "status": "WAITING_MATERIAL",
  "instructions": ["优先核对营业执照"],
  "progress": "已完成基础信息检查",
  "pendingMaterials": ["近三个月流水"],
  "toolResults": [{"tool": "company-search", "summary": "企业状态正常"}],
  "resumeCheckpoint": "等待用户补充流水",
  "expiresInSeconds": 86400
}
```

6. 点击“Execute”。
7. 预期HTTP 200；响应中的 `taskId` 为 `credit-review-001`，状态为 `WAITING_MATERIAL`。

`expiresInSeconds=86400`表示保存24小时；允许范围是60秒到30天。

### 10.2 提交第一轮对话

1. 展开 `POST /api/v1/short-term-memory/turns:commit`。
2. 点击“Try it out”。
3. 填写三个相同身份Header。
4. `Idempotency-Key` 输入 `credit-review-001-turn-001`。
5. Request body输入：

```json
{
  "taskId": "credit-review-001",
  "sessionId": "chat-001",
  "turnId": "turn-001",
  "userMessage": "请先检查企业基本资料",
  "assistantMessage": "基础资料已经检查完成",
  "occurredAt": "2026-07-30T10:00:00Z"
}
```

6. 点击“Execute”。
7. 预期HTTP 200、`messageCount=2`、`replayed=false`。
8. 不修改任何值再次点击“Execute”。
9. 预期仍为200、消息数仍为2、`replayed=true`，证明没有重复保存。

### 10.3 用新会话恢复同一任务

1. 展开 `POST /api/v1/short-term-memory/context:prepare`。
2. 点击“Try it out”。
3. 填写相同三个身份Header。
4. Request body输入：

```json
{
  "taskId": "credit-review-001",
  "sessionId": "chat-002",
  "query": "继续办理",
  "maxMessages": 20
}
```

5. 点击“Execute”。
6. 预期HTTP 200。
7. `sessionId`应为新的 `chat-002`。
8. `messages`中应召回 `chat-001` 的两条消息。
9. `workbench.pendingMaterials`应仍有“近三个月流水”。

这证明跨会话恢复依赖 `taskId`，而不是复用旧 `sessionId`。

### 10.4 验证用户隔离

1. 展开GET任务接口并点击“Try it out”。
2. `task_id`仍输入 `credit-review-001`。
3. Tenant和Agent保持不变。
4. 把 `X-User-Id` 改成 `user-demo-b`。
5. 点击“Execute”。
6. 预期HTTP 404。

404不会告诉调用方“另一个用户是否拥有同名任务”，避免越权信息泄露。

### 10.5 删除任务

1. 展开DELETE任务接口。
2. 点击“Try it out”。
3. 恢复 `X-User-Id=user-demo-a`。
4. `task_id`输入 `credit-review-001`。
5. 点击“Execute”。
6. 预期HTTP 204。
7. 再用GET读取，预期404。

## 11. 智能体为什么现在不能调用新服务

当前未完成以下运行链步骤：

```text
注册服务实现
→ 发布实现配置
→ 给智能体创建启用绑定
→ GenB校验服务凭证、智能体ID和绑定
→ 注入可信身份范围
→ 调用短期记忆服务
```

因此本轮不要拿测试智能体调用 `18705` 来判断“绑定是否生效”。智能体直接填写三个身份Header调用只适合本地组件开发测试，不能作为正式接入方式。

后续联通迭代需要单独实现：GenB运行入口、服务凭证校验、绑定解析、可信身份注入、超时重试和审计，然后再写智能体接入手册。

## 12. 常见错误

| 现象 | 原因 | 处理 |
|---|---|---|
| GenB接口403 | 未登录或角色缺少权限 | 重新登录；补 `component.read/configure` |
| 提示版本已存在 | 同组件已使用该版本 | 改为新的版本号，不覆盖历史 |
| 提示只支持OpenAPI 3.0/3.1 | 文档不是支持的OpenAPI版本 | 修改顶层 `openapi` |
| 提示缺少info或paths | 文档结构不完整 | 使用样例文件对照补齐 |
| 提示operationId重复 | 两个接口使用相同程序标识 | 为每个接口使用唯一operationId |
| YAML上传后格式仍为JSON | 文件扩展名不正确 | 使用 `.yaml` 或 `.yml` |
| 注册实现下拉框为空 | 契约仍为草稿 | 返回接口契约页签先发布 |
| 短期记忆ready返回503 | Redis模式配置错误或Redis不可达 | 检查环境变量与Redis，不会自动降级到内存 |
| 同幂等键返回409 | 相同键被用于不同请求正文 | 每个真实回合使用独立稳定键 |

## 13. 本轮验收勾选表

- [ ] 页面显示固定5个系统、14个组件。
- [ ] 短期记忆详情默认显示“接口契约”。
- [ ] 上传YAML后自动识别格式。
- [ ] 草稿显示5个接口。
- [ ] 查看抽屉显示请求方法、路径、operationId和响应。
- [ ] 草稿发布后状态为“已发布”。
- [ ] 注册实现只能选择已发布版本。
- [ ] 未保存服务实现。
- [ ] 未创建配置和智能体绑定。
- [ ] Swagger保存工作台成功。
- [ ] 新sessionId可以按taskId恢复。
- [ ] 换userId后读取返回404。
- [ ] 幂等重放不重复增加消息。
- [ ] 删除后读取返回404。

全部勾选后，表示“契约控制面”和“短期记忆独立服务”分别验收通过；不表示智能体调用链已经接通。
