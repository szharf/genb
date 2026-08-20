# 统一数据面网关 M5 完成报告

- 日期：2026-08-13
结论：Gate F 通过；允许进入上线前检查计划，不允许跳过该计划直接部署

## 1. 本次补验范围

针对检查点报告中唯一未验收缺口，在同一窗口实际运行了本地 Nginx、真实 GenB、统一数据面网关、专用 Redis、18714 测试智能体、短期记忆、长期记忆、规划推理和 Runtime Fake Provider。浏览器身份入口使用本地门户夹具，但授权码签发、兑换、Session Grant、Actor Token、绑定版本和能力调用均由真实 GenB 与真实网关完成。

## 2. 补验中发现并修复的问题

- 网关增加受控 `secret://core-components/runtime` 解析，只允许映射到显式环境变量或文件，拒绝路径穿越和未知别名。
- GenB 数据面 Controller 增加相对 context-path 的正确映射，修复部署后实际地址出现双 `/api/api/` 的问题，并保留旧映射兼容已有测试。
- 网关编译路由时统一去除上游地址尾部斜杠，避免 Nginx 拼接产生双斜杠。
- GenB Actor Token 的 `expiresAt` 从无时区 `LocalDateTime` 改为 UTC `Instant`。此前绑定版本相同，但网关因到期时间无时区而安全拒绝调用。
- Runtime Fake Provider 补齐长期记忆提取、客户对话和规划/Skill 验收所需的结构化输出；该 Provider 只替代外部付费模型，不替代三个真实组件进程。
- GenB 客户端普通智能体入口改为统一 `/agents/{agentId}/`，不再生成后端服务器裸端口地址。

## 3. 真实浏览器证据

`tests/m5_real_full_stack_browser.py` 已通过，标识为 `M5真实栈偏好-1786602796`。覆盖：

- admin 完成短期两轮记忆、长期记忆写入与跨会话召回、Skill 先澄清后生成、刷新恢复；
- test_user 无法检索 admin 的唯一长期记忆标识，并能完成自己的短期两轮记忆；
- 两个用户退出后访问受保护会话均返回 401；
- 组件调用实际到达 18705、18702、18712 和 18704，未使用确定性数据面 Adapter 替代组件。

截图位于 `genb-data-plane-gateway/artifacts/m5-real-browser/`。

## 4. 最终回归

| 范围 | 结果 |
|---|---|
| 数据面网关常规绿灯套件 | 53 passed，3 skipped；跳过项要求独立 Nginx/Redis 夹具，真实总验收已覆盖对应运行能力 |
| M0 红灯基线 | 保留为实现前失败规范，不纳入绿灯套件；其中普通智能体裸端口要求已转绿 |
| 数据面合同 | 9 passed |
| 18714 测试智能体 | 67 passed，1 个第三方弃用告警 |
| Runtime | 47 passed，3 个第三方弃用告警 |
| 短期记忆 | 11 passed，1 skipped |
| 长期记忆 | 31 passed，1 skipped |
| 规划推理 | 40 passed，4 skipped |
| GenB 后端 | 170 passed，1 skipped，0 failure/error |
| GenB 客户端 | 入口专项 7 passed；TypeScript 检查和 Vite 生产构建通过 |
| GenB 管理端 | Vite 生产构建通过 |
| 真实双用户浏览器 | 通过 |

组件套件跳过项为未注入专项外部环境的集成测试；同一轮真实总验收已经使用本地 PostgreSQL、Redis 和真实组件进程覆盖上线必需主路径。

## 5. Gate F 结论

检查点所述“GenB 与三个真实组件进程未在同一窗口经新数据面调用”的缺口已闭合。自动化、真实浏览器、身份隔离、刷新、退出和兼容入口均通过，因此 Gate F 通过。下一步只能执行 `20260812-PLAN-production-readiness-inspection-and-remediation.md`，上线前检查 Gate D 通过前仍禁止生产部署和切流。

## 6. 工作树保护

根仓库与 `gen-b` 子仓库原本均有用户和历史修改。本轮未执行 reset、checkout、clean、提交或推送，也未把整个脏工作树视为本轮成果。
