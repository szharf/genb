# GenB核心组件治理Iteration 4报告

## 1. 背景

Iteration 3已经打通固定五系统/14组件目录、Implementation注册、配置发布、智能体绑定和RBAC，但还缺少日常运维所需的停用、恢复、回滚和审计。服务凭证与组件会话如果先于这些治理能力落地，会导致已停用实现或错误配置仍可能被智能体使用。

## 2. 目标

在不开发前端、不连接远程数据库、不部署的前提下，通过GenB真实登录、JWT、Controller、Service和H2 JPA纵向链路，完成核心组件控制面的治理闭环，并确保审计不复制配置或秘密引用。

## 3. 实现范围

### 3.1 Implementation生命周期

- `POST /v1/core-components/{componentCode}/implementations/{implementationId}:disable`
- `POST /v1/core-components/{componentCode}/implementations/{implementationId}:enable`
- 停用Implementation后拒绝新增绑定。
- 即使绑定状态为`ENABLED`，停用Implementation也不会被生效解析。
- Implementation未恢复前不能恢复其绑定。

### 3.2 配置版本治理

- `GET /v1/core-components/{componentCode}/configs?implementationCode=...&profileCode=...`
- `POST /v1/core-components/{componentCode}/configs/{configId}:rollback`
- 列表按版本号倒序返回。
- 回滚源必须是已发布版本。
- 回滚不会修改历史记录，而是复制配置和secretRef引用，生成新的递增`PUBLISHED`版本。
- 新版本记录执行人、发布时间和`Rollback from version N`摘要。

### 3.3 绑定生命周期

- `POST /v1/core-components/{componentCode}/bindings/{bindingId}:disable`
- `POST /v1/core-components/{componentCode}/bindings/{bindingId}:enable`
- 停用后生效解析失败；恢复后原绑定重新生效。
- 继续保留`agentId + componentId`唯一主绑定约束，避免停用后创建第二条冲突记录。

### 3.4 管理审计

- 新增`component_audit_events`实体和Repository。
- `GET /v1/core-components/{componentCode}/audits`返回最近200条记录。
- 记录当前GenB用户名、动作、目标类型、目标ID、结果和时间。
- 覆盖Implementation注册/启停、配置草稿/发布/回滚、绑定创建/启停。
- 审计表和响应不包含配置JSON、`secretRefs`、密码或secret值。

## 4. 权限

- 配置查询和审计查询：`component.read`。
- Implementation注册/启停、配置草稿/发布/回滚：`component.configure`。
- 绑定创建/启停：`component.bind`。
- 权限仍由`@PreAuthorize`在后端强制执行，页面隐藏不能替代服务端授权。

## 5. 测试方法与结果

每项能力先通过MockMvc公开HTTP测试得到失败结果，再实现最小行为：

1. 绑定启停接口最初返回404，完成状态机后通过。
2. 配置列表最初返回405，列表和回滚完成后通过。
3. Implementation启停接口最初返回404，启停与绑定门禁完成后通过。
4. 审计查询最初返回404，审计实体、写入和查询完成后通过。

最终执行：

```text
cd D:\code\opencode\genb\gen-b\gen-b-backend
mvn -q test
```

Surefire结果：13个报告，93项测试，0失败，0错误，0跳过。`git diff --check`通过；审计模型秘密关键词扫描无命中。

## 6. 未包含范围

- 未开发Vue管理页面。
- 未签发服务凭证或组件会话。
- 未实现Credential、Health和TestRun模块。
- 未提供生产数据库显式迁移脚本。
- 未连接远程PostgreSQL/Redis，未调用外部模型，未部署。
- 未提交`target`、Vite缓存、中英文`dist`或其他既有工作区产物。

## 7. 风险与后续

- 生产仍依赖Hibernate `ddl-auto:update`，在正式环境使用新表前必须先补显式迁移、备份和回滚演练。
- 审计目前记录成功状态变更；被拒绝的请求由既有安全/操作日志承接，后续应统一失败审计与requestId。
- 配置版本号依赖唯一约束处理并发冲突；多管理员高并发场景后续应增加明确的冲突响应和重试策略。
- 下一迭代建议实现短期服务凭证、可吊销组件会话、scope与绑定快照，并保持高频组件调用不经过GenB控制面。
