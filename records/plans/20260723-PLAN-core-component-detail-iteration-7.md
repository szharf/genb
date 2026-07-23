# 核心组件平台 Iteration 7 计划：组件详情治理视图

## 一、交付目标

在 Iteration 6 的真实目录页基础上增加稳定详情入口。详情页不拼接多个前端猜测接口，而由 GenB 后端提供一次性、权限受控的治理快照，确保实施状态、配置版本、绑定和审计来自同一个控制面。

## 二、后端读模型

新增 `GET /v1/core-components/{componentCode}`，返回：

- 固定组件目录信息。
- 该组件全部 Implementation 元数据。
- 该组件全部配置版本元数据。
- 该组件全部智能体绑定元数据。
- 最近 200 条管理审计。

接口只要求 `component.read`，不返回配置 JSON、secretRef 正文或服务凭证明文。

## 三、前端数据流

```text
组件卡片 select
  → Router /core-components/:componentCode
  → useCoreComponentDetail.load(componentCode)
  → GET /v1/core-components/{componentCode}
  → 详情头部 + 四类只读治理表
```

所有异步状态由 composable 持有；展示组件只接收只读 props，通过 emit 发出返回、刷新等意图。

## 四、验收策略

1. 后端集成测试先覆盖空详情、包含实现/配置/绑定/审计的详情、权限拒绝和不存在组件。
2. 前端纯逻辑测试覆盖状态/时间格式映射等可独立逻辑。
3. 双语构建验证路由和 SFC 编译。
4. 本地浏览器使用真实管理员 Token，从目录卡片进入详情，检查四个标签页和返回链路。
5. 最终只读核对远程核心组件 7 表物理外键数仍为 0。

## 五、下一轮

Iteration 8 在该详情视图上增加写操作：Implementation 注册/启停、配置草稿/发布/回滚、智能体绑定/启停。写操作必须逐项使用现有后端权限和审计，不在前端模拟状态。
