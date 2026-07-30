# 规划与推理引擎接入 GenB 与测试智能体验收报告

日期：2026-07-30

## 1. 结论

`PLANNING_REASONING`已经完成从独立服务到GenB控制面、管理端双模式测试台、专用测试智能体和客户端测试页面的完整联通。它不再只是一个独立端口：GenB现在真实保存并校验契约、实现、配置和绑定，智能体必须使用自己的长期服务凭证申请组件会话，规划服务再次校验短时Actor Token后才执行澄清、生成、校验或修订。

## 2. 实现结果

- GenB新增`PLANNING_REASONING_V1`调用适配器和专用测试接口。
- 固定组件已注册发布OpenAPI `1.0.0`契约，共解析7个HTTP操作。
- 已注册实现`planning-reasoning-service-v1`、发布`default v1`配置。
- 已创建并启用`standalone-planning-test-agent`绑定。
- 测试智能体新增`/api/planning`，从GenB绑定结果读取真实`baseUrl`，不写死规划服务地址。
- 管理端提供管理员服务直测和智能体绑定测试，支持四种操作和可编辑默认JSON。
- 客户端新增规划测试智能体页面，浏览器不接触服务凭证。
- 本地启动脚本使用DPAPI保护长期凭证和内部令牌，并幂等恢复注册数据。

## 3. 本地注册数据

| 对象 | 当前值 |
|---|---|
| 契约 | ID 2，`1.0.0 / PUBLISHED`，7个操作 |
| 实现 | ID 5，`planning-reasoning-service-v1 / REGISTERED / PLANNING_REASONING_V1` |
| 配置 | ID 7，`default v1 / PUBLISHED` |
| 绑定 | ID 7，`standalone-planning-test-agent / ENABLED` |

没有创建物理外键；远程开发库只追加/更新本任务记录，未批量删除数据。

## 4. 验收结果

### 自动化

- GenB后端全量：127项通过，0失败。
- 测试智能体：17项通过。
- GenB客户端：13个测试文件、34项通过。
- 管理端核心组件纯逻辑测试全部通过。
- 管理端中文、英文构建通过。
- 客户端中文、英文构建通过。

### 真实HTTP

- 管理员服务直测：返回`SERVICE_DIRECT + NEEDS_CLARIFICATION`。
- 智能体绑定调用：需求澄清返回3个问题。
- Skill生成：生成v1且自校验通过。
- Skill校验：返回`valid=true`。
- 失败修订：相同Skill生成v2，v1未覆盖。
- 错误凭证：组件会话返回HTTP 403。
- 停用绑定：智能体真实调用失败；恢复绑定后重新可用。

### 真实浏览器

- 管理员服务直测成功。
- 管理端智能体绑定测试成功。
- 客户端专用测试智能体成功。
- 浏览器控制台错误：0。
- 证据：`records/reports/assets/20260730-planning-dual-testbench.png`、`records/reports/assets/20260730-planning-test-agent.png`。

## 5. 安全结果

- 一个测试智能体只有一个活动长期服务凭证；轮换会吊销旧凭证。
- 凭证只存在于服务端进程和当前Windows用户可解密的DPAPI文件。
- 管理员服务直测不发送智能体服务凭证。
- Actor Token有效期仍由GenB限制在60到900秒。
- 错误响应不回显服务凭证、Actor Token或上游响应正文。

## 6. 操作入口

详细逐点击文档：`docs/operation/PLANNING_REASONING_GENB_AND_TEST_AGENT_GUIDE.md`。
