# 统一数据面网关M0现状与失败基线

- 日期：2026-08-12
范围：`D:\code\opencode\genb`本地工作区；未连接服务器或生产依赖

## Git保护基线

- 根仓库与`gen-b`子仓库均位于`codex/core-components-pre-m5-20260806`。
- 两处工作树均有大量用户/同事既有修改；本阶段未重置、清理、合并或覆盖。
- 本轮新增限定为ADR、威胁模型、合同、M0测试和记录；现有业务Implementation不修改。

## 已验证现状

| 行为 | 代码证据 | 当前结论 |
|---|---|---|
| 普通智能体入口 | `gen-b/gen-b-client/src/utils/agentLaunch.ts` | 普通智能体仍生成`http://47.116.69.17:{port}`裸入口 |
| 18714登录 | `control-system-test-agent/.../web.py` | 智能体自身实现`/auth/login`、callback、Redis会话和Cookie |
| 18714能力调用 | `control-system-test-agent/.../clients.py`与`orchestrator.py` | 智能体自行取得Component Session并携带服务凭证、Actor Token直连组件 |
| Manifest通用性 | `ComponentManifestImportService.java` | Adapter与Scope映射仅覆盖短期、长期、规划三个能力 |
| 数据面项目 | 根目录与全文检索 | `genb-data-plane-gateway/`业务Implementation不存在 |
| 正式路由 | 当前本地配置与全文检索 | 无`/agents/{agentId}/`与`/component-api/`正式网关实现 |

## M0红色验收场景

安全验收通过计划中的公开HTTP Interface运行。当前没有数据面进程，预期全部为红；这证明失败来自能力缺失，不把跳过项当作通过。

1. 旧裸端口入口无法建立统一用户身份。
2. 浏览器伪造`X-GenB-*`身份Header必须被拒绝/覆盖。
3. 用户提供的未知上游地址不得参与路由。
4. 未绑定能力必须返回稳定403 Problem Details。
5. 停用Implementation必须返回稳定503 Problem Details。
6. 过期身份Token和撤权缓存不得继续放行。
7. 响应与错误不得泄漏Secret、Actor Token或真实上游。
8. 两个用户不得共享有状态数据。

## 运行方式

合同测试：

```powershell
& <python> -m unittest contracts.tests.test_data_plane_contracts -v
```

红色验收：

```powershell
& <python> genb-data-plane-gateway/tests/test_m0_security_red.py -v
```

默认目标为`http://127.0.0.1:18080`，可用`GENB_GATEWAY_BASE_URL`覆盖。M0不得启动伪实现让测试虚假转绿。

## Gate A结论规则

- ADR与详细计划一致。
- 威胁及停止条件有编号并映射后续Gate。
- JSON Schema和OpenAPI可被机器解析并通过合同测试。
- 红色测试确实失败，且失败根因是数据面Implementation尚不存在或对应安全行为尚未实现。
- 满足以上条件后仅允许进入M1；不代表任何数据面功能已经交付。
