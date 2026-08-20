# 三个核心组件独立服务收敛M5完成报告

## 1. 背景

短期记忆、长期会话记忆、规划与推理已分别完成独立服务和GenB统一接入。M5负责总回归、真实浏览器验收、契约一致性、安全审计、旧入口清理和文档收口。

## 2. 目标

- 证明三个组件能通过独立服务、GenB控制面和18714客户智能体完成真实调用。
- 保留统一登录识别修复与`riskLevel=UNKNOWN`的保守归一化修复。
- 只保留`http://localhost:18714/`客户入口，删除9100旧代理和旧页面。

## 3. 范围与边界

本次只操作本地代码、本地Redis、本地PostgreSQL和本地进程。没有连接服务器、修改服务器Nginx或服务器数据库。开发与任务文档按用户要求保留在工作区，不纳入当前提交。

## 4. 实施结果

1. 从失败基线开始恢复SSO源码：旧入口测试先因Vite仍代理`/core-agent/`失败，恢复独立18714启动地址和移除代理后转绿。
2. 后端SSO测试先因缺少授权DTO、`AgentSsoService`、Redis存储和依赖而编译失败，恢复一次性授权码、Redis会话、服务凭证换票、Session Grant和审计实现后转绿。
3. 发现18714本地服务凭证已失效，轮换为凭证ID 95并用DPAPI保存；同步重启18714和18704 Runtime，恢复换票与模型调用。秘密未输出到报告或日志。
4. 浏览器验收发现favicon 404；新增失败测试后使用内联SVG favicon修复，18714全量从63项增至64项，浏览器控制台清零。
5. 9100旧`/core-agent/`不再代理，当前仅返回`410 Gone`墓碑；不存在可使用的第二套智能体入口。

## 5. 自动化验收

| 范围 | 结果 |
|---|---|
| GenB后端 | 154 passed，1 skipped，0 failures/errors |
| GenB客户端 | 41 passed；生产构建通过 |
| 短期记忆 | 11 passed，1 skipped |
| 长期记忆 | 31 passed，1 skipped |
| 规划与推理 | 40 passed，4 skipped |
| 18714测试智能体 | 64 passed |
| Control System | 50 passed，3 skipped |
| Runtime System | 45 passed |
| Manifest合同 | 2 passed |

跳过项均为未向本轮pytest进程注入真实Redis密码或PostgreSQL DSN；不是用失败冒充通过。M4前置验收已使用本地真实Redis/PostgreSQL验证运行态、绑定、迁移和三组件会话。本轮没有使用服务器环境补证据。

## 6. 浏览器与运行态验收

- 统一门户授权后回到`http://localhost:18714/`。
- `genb_agent_session`为`HttpOnly=true`、`SameSite=Lax`、`Path=/`。
- 短期记忆：两轮对话准确复述第一轮内容并显示“本次交流记忆验证成功”。
- 长期记忆：对话历史从9条增至10条；新会话中找回旧会话偏好并显示“跨会话长期记忆验证成功”。
- 规划与推理：第一轮先返回澄清问题，完整回答后生成2750字Skill结果。
- 刷新后仍停留在18714并保持会话；退出返回303、会话Cookie被清除，再访问根入口重新`303 -> /auth/login`。
- 最终浏览器控制台错误为0；证据截图位于本地忽略目录`.logs/customer-core-agent-local/m5-browser-acceptance.png`。

## 7. 契约与安全

- Manifest与静态/运行时OpenAPI路径集合一致：短期6/6、长期9/9、规划15/15。
- Interface版本一致：短期1.1.0、长期1.0.0、规划1.1.1。
- `git diff --check`通过；未发现凭证、一次性授权码或Session Grant日志输出。
- `riskLevel=UNKNOWN`回归测试和保守归一化逻辑仍在。

## 8. 结论与后续

Gate F通过，三个核心组件独立服务收敛任务M0-M5完成。后续新增组件继续遵守“一组件一公共服务真源、GenB统一控制面、Manifest/OpenAPI/运行时一致、测试先行、18714自然语言验收”的规则；Knowledge Base仍由同事通过长期记忆内部Adapter接入。
