# GenB 核心组件详情治理写操作 Iteration 8 实施报告

## 一、结果

在 Iteration 7 只读详情快照上，完成管理员可真实操作的治理闭环：

- Implementation 注册、停用和恢复。
- 配置草稿创建、发布和历史版本回滚（回滚生成新版本，不覆盖历史）。
- 真实智能体绑定、停用和恢复。
- 每次成功写操作刷新详情快照，并展示后端生成的管理审计。

本轮不新增后端接口或数据表，复用已有控制面 API、RBAC、状态机和审计规则；未部署。

## 二、前端实现

### 2.1 API 与状态编排

`coreComponent.js` 封装 7 类写请求：注册实现、实现启停、新建配置、发布、回滚、绑定智能体和绑定启停。

`useCoreComponentGovernance.js` 统一处理：

- 操作中状态。
- HTTP/业务错误归一。
- 真实智能体候选加载。
- 成功后由详情页重新拉取聚合快照。

### 2.2 三个独立弹窗

- Implementation 弹窗：校验编码、负责人、接口版本、HTTP/HTTPS 服务与健康检查地址。
- 配置弹窗：只允许选择已启用实现，校验 JSON 顶层为对象，将 secret 作为引用而非明文收集。
- 绑定弹窗：从真实智能体列表选择，只展示所选实现的 `PUBLISHED` 配置版本。

表格只发出治理意图，确认弹窗、请求、成功/失败反馈和刷新由详情容器统一编排。中英文文案同步补齐。

## 三、真实页面验收

在本地 `http://localhost:9100/genb/core-components/SHORT_TERM_MEMORY` 通过页面完成全链路，并保留可追溯的 Iteration 8 验证数据：

| 对象 | 验收值 | 最终状态 |
|---|---|---|
| 组件 | `SHORT_TERM_MEMORY` | 目录与详情正常 |
| Implementation | `iteration8-governance-20260723-v1` | `REGISTERED` |
| 配置档案 | `iteration8-default` | v1 `PUBLISHED`，回滚新版本 v2 `PUBLISHED` |
| 智能体 | `agent-sdlc-ai-testing` | 绑定 v2，`ENABLED` |
| 审计 | 注册、发布、回滚、绑定及启停 | 9 条 |

验收期间未删除任何数据。注册地址使用本地验证占位端口，本轮不包含记忆执行服务健康检查或部署。

## 四、自动验证

- 前端表单模型测试：通过，覆盖 JSON、非对象 JSON、secret 引用去重和已发布配置过滤。
- 管理端中文生产构建：通过，2309 modules。
- 管理端英文生产构建：通过，2309 modules。
- 后端核心组件专项集成测试：14/14 通过。
- 后端全量测试：105/105 通过。
- `git diff --check`：通过。
- 远程 `bank_agent_db` 中 6 张本轮相关控制面表的物理外键：0。

仓库定义了 `lint` 命令，但当前没有 ESLint 配置文件，因此 ESLint 8.57.1 在启动检查时退出，未为本轮擅自扩大范围生成全局配置。构建仍有项目既有的大 chunk 警告。

## 五、数据库与安全边界

- 没有新增表、字段或物理外键。
- 前端不展示配置正文、secret 值或服务凭证。
- 重复有效绑定、非法状态迁移、未发布配置绑定和越权请求仍由后端作为最终门禁。
- 本轮未部署，未修改 Nginx 或公网产物。

## 六、提交

- GenB 源码提交：`2d7a4f0 feat: add core component governance actions`
