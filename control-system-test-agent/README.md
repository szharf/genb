# Control System Test Agent

用于GenB核心组件验收的薄HTTP调用方。同一份代码既可通过CLI运行`memory-test-a`、`memory-test-b`隔离实例，也可作为`standalone-memory-test-agent`的HTTP聊天后端；不复制项目、不共用凭证，也不依赖旧Runtime SDK。

当前链路：

1. 携带用户JWT和本实例服务凭证向GenB申请`SHORT_TERM_MEMORY`组件会话。
2. 携带服务凭证和GenB RS256 Actor Token向Control System准备短期上下文。
3. 使用确定性测试回答器生成回答，避免模型Provider故障污染记忆验收。
4. 向Control System提交本轮对话；准备失败时无上下文降级，提交失败时返回回答并给出告警。

## 测试

```powershell
$python = 'D:\code\opencode\genb\gen-o\backend\.venv\Scripts\python.exe'
& $python -m pytest -q
```

## 单实例运行

从`.env.example`了解配置项，但不要把真实Token或凭证写入Git。运行时注入环境变量：

```powershell
$env:AGENT_ID = 'memory-test-a'
$env:GENB_BASE_URL = 'http://127.0.0.1:18581/api'
$env:CONTROL_SYSTEM_BASE_URL = 'http://127.0.0.1:18701'
$env:SERVICE_CREDENTIAL = '<GenB签发且仅属于A的凭证>'
$env:USER_TOKEN = '<当前测试用户JWT>'
$env:PYTHONPATH = 'src'
& $python -m control_system_test_agent.main --session-id 'acceptance-a' --message '我偏好低风险产品'
```

切换到B时只替换`AGENT_ID`和`SERVICE_CREDENTIAL`。输出不会包含凭证或Actor Token。

## standalone-memory-test-agent聊天服务

服务端从环境变量读取长期服务凭证，浏览器只提交用户JWT和聊天内容：

```powershell
..\scripts\start_standalone_memory_test_agent.ps1 -Password '<管理员登录密码>'
```

服务监听`127.0.0.1:18711`，提供`GET /health/live`和`POST /api/chat`。GenB客户端通过同源路径`/test-agent/api/chat`代理调用，聊天入口为`http://localhost:9100/agents/standalone-memory-test-agent/chat`。

每轮调用顺序为：向GenB申请绑定组件会话、从动态绑定中取得短期记忆地址、准备上下文、生成确定性测试回答、提交本轮消息。该回答器专门用于验证记忆链路，不代表正式业务智能体的大模型回答能力。

## 安全边界

- 只接受HTTP(S)服务地址，生产环境的HTTPS强制由服务端与部署门禁负责。
- 每次HTTP调用由`httpx.Timeout`设置明确超时。
- 上游失败只保留operation、HTTP状态和requestId，不保留请求正文、响应正文或认证Header。
- 本项目只做HTTP/DTO/超时/错误映射和测试编排；Redis、身份验证、TTL与记忆策略仍属于Control System。
