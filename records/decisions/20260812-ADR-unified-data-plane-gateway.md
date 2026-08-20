# ADR：以统一数据面网关替代智能体常态直连

- 状态：已采纳，待实现
- 日期：2026-08-12
- 范围：智能体统一入口、核心能力调用、身份、路由、Adapter 与缓存
- 替代：`20260805-ADR-fourteen-component-services-five-system-classification.md`第4、5条中“不强制数据代理、智能体常态直连组件”的调用结论
- 保留：十四个稳定能力码、十四组件独立交付、五系统仅作分类、长期记忆仍是一个能力

## 背景

当前18714自行实现门户SSO、Redis会话和Component Session，普通智能体仍可由客户端跳转到裸`IP:port`。三个已交付组件要求智能体持有服务凭证并理解GenB Actor Token；同事交付的其他服务未必实现这套身份合同。继续直连会把登录、凭证、Adapter、隔离和审计分散到每个智能体。

## 决策驱动

- 一次登录改造应覆盖全部智能体入口。
- GenB保持低频控制面，不承载SSE、文件和每次能力调用正文。
- 服务方可以自由命名和部署，只交付接口、认证、隔离与运行约束。
- 浏览器和智能体不得获得服务Secret、门户Token或上游真实地址。
- 一期必须能在现有资源上单实例运行，并保留未来拆分能力。

## 候选方案

1. 每个智能体继续实现SSO并直连组件：拒绝，重复身份、凭证和Adapter逻辑。
2. 所有字节流进入GenB Java后端：拒绝，控制面与高频数据面耦合。
3. 访问网关和能力网关分别部署：保留为未来拆分方向，一期运维成本过高。
4. Nginx承载智能体字节流，一个轻量数据面应用提供两个内部Module：采用。

## 决定

1. Nginx统一暴露`/agents/{agentId}/`，通过Access Decision Module的内部Interface鉴权后直接流式代理到已发布上游。
2. 智能体通过Capability Invocation Module的统一Interface按稳定`capabilityCode + operationId`调用能力，不直接选择实现地址。
3. GenB管理能力、Implementation、Adapter、绑定、策略、配置版本、Secret引用和网关机器身份，只下发不含秘密的完整快照。
4. Adapter Registry只选择随网关发布、经过代码审查的Adapter；一期禁止动态执行上传脚本。
5. 当前三个组件继续验证Actor Token与隔离键；由网关代智能体取得短时Actor Token。外部服务只接收其自身需要的机器认证和最少隔离信息。
6. 数据面使用L1与专用Redis缓存；高风险撤权目标5秒内生效，低风险最近有效配置宽限最多15分钟。
7. 生产上游必须禁止浏览器绕过网关直连；不能证明隔离的有状态智能体标记为`UNSUPPORTED_MULTI_USER`。

## Module与Seam

- Access Decision Module Interface：`authorize(agentId, sessionCookie, requestMeta)`；隐藏会话、授权、路由和身份Token签发。
- Capability Invocation Module Interface：`invoke(capabilityCode, operationId, context, payload)`；隐藏绑定、Adapter、Secret、隔离、错误和审计。
- Control Snapshot、Secret Resolver、Cache、Audit Sink是内部Seam；每个远程依赖至少有生产Adapter和内存测试Adapter。
- Nginx是字节流Adapter，不是数据面应用内部Implementation。

## 后果

正面后果：统一入口、凭证集中、智能体与服务实现解耦、GenB不承载高频正文、替换实现不修改所有智能体。负面后果：新增网络跳转和单实例故障点，需要维护Adapter、缓存一致性与生产网络限制。

## 确认方式

- 机器可读合同及合同测试通过。
- M0安全验收测试先稳定为红；后续按M1-M4逐项转绿。
- M5用两个用户、多个智能体、三个现有Adapter和一个非标准Fake Adapter完成浏览器、隔离、故障与性能验收。
