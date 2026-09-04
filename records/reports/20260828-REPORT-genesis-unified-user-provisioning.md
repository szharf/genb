# Genesis 统一模块新增用户功能完成报告

- 日期：2026-08-28
- 范围：GenB 后端、管理端、业务客户端、数据库增量脚本和本地验收
- 状态：本地完成，待独立生产上线审批

## 交付结果

- 管理员可在“Genesis 用户与平台权限”页面通过一次 `POST /api/v1/genesis/admin/access-users` 创建统一用户。
- GenO 目录读取与稳定 ID 核对在本地事务开始前完成；缺失、重复、禁用或目录不可用时不会写入本地数据库。
- GenB 用户、Genesis 用户、全局角色、GenB 映射授权、GenC 映射/授权/平台角色、GenO 精确映射授权及成功审计在同一事务提交。
- 重复用户名和启用外部映射冲突不会覆盖已有用户；数据库增量脚本增加部分唯一索引并在存量冲突时 fail-closed。
- 新用户默认 `password_change_required=true`。GenB 与 Genesis 改密入口共用统一服务，一次改密同步两张用户表的 BCrypt 哈希和状态。
- 后端对首次改密用户实施 HTTP 428 门禁；中英文 Genesis 门户和 GenB 客户端提供改密引导。
- 请求、响应、审计和日志均不返回或记录初始密码、密码哈希、Token 或 GenO 服务端密钥。

## 验收证据

- 后端：`mvn test`，179 项执行、其中 1 项按原条件跳过、0 失败。
- 管理端：18 项 Node 测试通过；`npm run build:zh`、`npm run build:en` 通过。
- 客户端：15 个测试文件、43 项测试通过；`npm run build:zh`、`npm run build:en` 通过。
- 专项覆盖：非管理员 403、非法参数 400、重复冲突 409、GenO 无效 422、GenO 不可用 503、首次改密 428、GenO 失败零写入和事务末端异常全回滚。
- 结构检查：`git diff --check` 通过；生成的构建目录不纳入提交。

## 上线前置条件

1. 对目标 PostgreSQL 执行只读重复映射查询并备份。
2. 显式执行 `V20260825_01__add_unified_user_provisioning_constraints.sql`，不能依赖 `ddl-auto=update`。
3. 按“数据库迁移 → 后端 → 中英文管理端和客户端”顺序发布。
4. 重新执行管理员创建、普通用户 403、重复 409、GenO 不可用零写入和首次改密的生产前隔离验收。
5. 继续遵守服务器容量 Gate；本报告不授权生产部署、生产数据库写入或 Nginx 修改。
