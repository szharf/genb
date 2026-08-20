# GenB Data Plane Gateway

M2 提供统一浏览器入口，M3 提供统一核心能力调用，M4 提供缓存一致性、主动失效、审计缓冲与故障恢复。Nginx 通过 `auth_request` 获取发布路由和短时身份 Token，并直接代理智能体的 SSE/WebSocket 字节流；能力调用由 ASGI 应用校验身份和绑定后交给编译期 Adapter。

核心边界：

- `Gateway Session`：随机 Cookie，服务端 Redis 保存，Key 只含 SHA-256 摘要。
- `Access Decision`：联合检查 session、agent、用户授权、请求路径和发布路由。
- `Identity Token`：RS256、固定 audience、最长 60 秒，并公开 JWKS。
- `Control Plane`：唯一机器身份交换一次性 code、撤销 session grant。
- `Capability Invocation`：闭合调用信封、逐主体限流、幂等、超时、熔断和统一 Problem Details。
- `Adapter Registry`：短期记忆、长期记忆、规划推理、推理兼容及异构 Fake 均为审查后的编译期模块，不执行上传脚本。
- `Secret/Actor Token`：快照只保存引用；网关运行时解析 Secret，并用 Gateway Session Grant 向控制面换取短时 Actor Token。
- `Runtime State`：完整快照按单一版本原子编译，LKG 持久化到 Redis；2 秒轮询兜底，高风险旧配置 5 秒失败关闭，低风险宽限上限 15 分钟。
- `Active Invalidation`：控制面发布配置或撤权后发送机器身份保护的闭合失效事件；会话 L1 在 Redis 写失败时保留拒绝墓碑，避免旧会话恢复后回生。
- `Audit Buffer`：有界 Redis Stream 缓冲，单批最多 100 条；仅在控制面完整接收后删除，不进行无限重试。
- `Nginx`：关闭浏览器 Header 整体透传，重建业务 allowlist 与可信 `X-GenB-*`；关闭响应/请求缓冲支持 SSE 和 WebSocket。

本地 Gate C 使用端口：网关 `18080`、Nginx `18081`、无状态 Fake `19001`、身份 Fake `19002`、独立 Redis `16380`。配置位于 `nginx/genb-gateway.local.conf` 与 `redis/local-gate-c.conf`。

运行测试前启动独立 Redis、本地开发栈和 Nginx，然后设置：

```powershell
$env:GENB_NGINX_E2E='1'
$env:GENB_REDIS_E2E='1'
python -m unittest discover -s tests -p 'test_m2*.py' -v
```

未设置环境变量时，真实 Nginx/Redis 用例会明确跳过，纯内存与合同用例仍运行。

M3 纯本地回归：

```powershell
$env:PYTHONPATH='genb-data-plane-gateway'
python -m unittest genb-data-plane-gateway.tests.test_m3_capability_invocation genb-data-plane-gateway.tests.test_m3_adapters genb-data-plane-gateway.tests.test_m3_configuration_and_control genb-data-plane-gateway.tests.test_m3_heterogeneous_fake_e2e -v
```

M4 本地回归（真实 Redis 使用独立 `16380` 端口）：

```powershell
$env:GENB_REDIS_E2E='1'
python -m pytest tests --ignore=tests/test_m0_security_red.py -q
```

M5 增加了可由环境变量完整装配的运行工厂、健康检查、非 root/只读容器、20 用户/20 组件质量门禁和真实 Chrome 验收脚本。运行时 Secret 优先通过 `*_FILE` 注入；完整变量表、启动顺序和清理步骤见 `../docs/operation/UNIFIED_DATA_PLANE_GATEWAY_LOCAL_ACCEPTANCE_GUIDE.md`。

```powershell
Set-Location D:\code\opencode\genb\genb-data-plane-gateway
$env:GENB_NGINX_E2E='1'
$env:GENB_REDIS_E2E='1'
python -m pytest tests --ignore=tests/test_m0_security_red.py -q
python tests\m5_full_stack_browser.py
python tests\m5_browser_acceptance.py
python tests\m5_three_experiences_browser.py
docker compose -f compose.local.yaml config -q
```

`m5_full_stack_browser.py` 使用确定性的本地验收 Adapter 验证统一入口、18714 页面和能力调用边界，不等同于“GenB 与三个真实组件进程同时运行”的 Gate F 证据。只有后者也完成后，才能把 Gate F 标记为通过并进入上线前检查。
