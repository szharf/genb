# GenB 核心组件管理端 Iteration 6 实施报告

## 一、完成结果

本轮交付了核心组件管理端第一版目录页，并把“设计允许外键关系、实际数据库不创建物理外键”落实到了代码、测试、迁移脚本和远程开发库。

管理端现在通过真实 `/v1/core-components` 接口展示固定五大系统和 14 个核心组件，不提供新增或删除固定目录的入口。页面支持关键字、系统、交付状态筛选，以及重置、刷新、加载、空数据和失败重试状态。

## 二、页面实现

页面采用以下边界：

- 路由页只组合核心组件目录容器。
- API Module 只封装核心组件 HTTP 请求。
- composable 负责请求状态、筛选条件、系统选项和分组派生数据。
- 筛选组件通过 props/`v-model`/emit 与容器通信。
- 卡片组件只展示名称、编码、契约版本和交付状态。

中文构建使用 `systemNameZh/componentNameZh`，英文构建使用 `systemNameEn/componentNameEn`。页面不包含前端假组件数据。

## 三、数据库无物理外键处理

### 1. 发现

远程 `bank_agent_db` 的 7 张核心组件控制面表已经由 Hibernate `ddl-auto:update` 创建，其中存在 6 个物理外键：

- `core_components.system_id -> core_systems.id`
- `component_implementations.component_id -> core_components.id`
- `component_config_versions.implementation_id -> component_implementations.id`
- `agent_component_bindings.component_id -> core_components.id`
- `agent_component_bindings.implementation_id -> component_implementations.id`
- `agent_component_bindings.config_version_id -> component_config_versions.id`

### 2. 代码门禁

以上 6 个 JPA 逻辑关联均显式使用 `ConstraintMode.NO_CONSTRAINT`。新增 H2 metadata 测试，确保 Hibernate 生成的 7 张控制面表不存在 imported foreign key。

### 3. 远程迁移

2026-07-23 在远程开发库执行兼容迁移：

| 表 | 迁移前行数 | 迁移后行数 |
|---|---:|---:|
| `core_systems` | 5 | 5 |
| `core_components` | 14 | 14 |
| `component_implementations` | 0 | 0 |
| `component_config_versions` | 0 | 0 |
| `agent_component_bindings` | 0 | 0 |
| `component_audit_events` | 0 | 0 |
| `service_credentials` | 0 | 0 |

迁移在一个事务中删除 6 个 `FOREIGN KEY` 约束；没有执行 `DELETE`、`TRUNCATE`、`DROP TABLE` 或字段删除。行数核对一致后提交，最终这 7 张表的物理外键数量为 0。

仓库同时保留：

- `db/migrate_core_component_foreign_keys_to_logical.sql`
- `db/verify_core_component_schema.sql`

## 四、验证结果

- H2 无物理外键专项测试：1 项通过。
- GenB 后端全量测试：102 项通过，0 失败。
- 目录筛选纯逻辑测试：通过。
- 管理端中文生产构建：通过。
- 管理端英文生产构建：通过。
- 本地真实浏览器验收：5 个系统、14 张卡片、14 个状态标签、搜索和重置通过，浏览器控制台 0 错误。
- `git diff --check`：通过。
- ESLint：仓库当前没有 ESLint 配置文件，因此无法作为本轮门禁；未自动生成配置以避免扩大修改范围。

构建仍有项目既有的大 chunk 警告，不影响本轮功能正确性。

## 五、未包含和下一步

本轮页面只完成固定目录查询。下一轮继续开发组件详情治理页面，包括实现注册、配置版本、智能体绑定、服务凭证和审计；之后再进入 Control System 的短期记忆、长期记忆执行服务和独立测试台。

生产发布仍需把 Hibernate `ddl-auto:update` 从发布流程中移除，改为显式 SQL 迁移加 `validate`。当前已通过 JPA 标注保证本轮六个逻辑关联不会再次自动生成物理外键。

## 六、提交

- GenB 源码提交：`d6df8c0 feat: add core component catalog console`
