# 任务：补齐张涛统一用户与平台权限

### 1. 背景

黄令湖、徐浩健、胡正尧的统一登录和平台权限已于 2026-07-27 完成。2026-08-24 在保持三人现有密码、角色和映射不变的前提下，补齐张涛的 GenB、Genesis、GenC 与 GenO 统一身份链路。

### 2. 目标与边界

- 张涛统一用户名为 `zhangtao`，GenB 与 Genesis 均为启用的 `ADMIN`。
- GenC 使用 Genesis 稳定身份映射，分配平台角色 `ADMIN` 并开通入口。
- GenO 只绑定既有、唯一、启用的同名 `admin` 用户，不创建或修改 GenO 用户。
- 黄令湖、徐浩健、胡正尧只做回归验证，不重置密码、不覆盖权限。
- 初始密码按已确认的团队规则设置，明文不写入报告、Git 或日志。

### 3. 安全前置检查

写入前通过 Genesis 正式管理接口读取 GenO 用户目录：四个目标用户名均只有一条同名记录；`zhangtao` 为启用状态、角色为 `admin`，并具有稳定外部用户 ID。Genesis 管理列表中前三人配置完整，`zhangtao` 为 0 条。

因此满足“GenO 同名用户不存在或不唯一时，在任何写入前停止”的 fail-closed 条件。

### 4. 执行结果

1. 先建立失败基线：`zhangtao` 的 GenB 登录返回业务码 401。
2. 在共享 GenB 数据库事务内新增唯一的 `zhangtao` 源用户，密码只保存为 BCrypt 哈希，并关联既有 `ADMIN` 角色。
3. GenB 登录转绿，确认账号启用且具有 `ADMIN`。
4. 调用 `POST /v1/genesis/sync/gen-b-users`，新增 1 个 Genesis 用户、1 个 GenB 映射和 1 个 GenB 授权。
5. 调用 Genesis 管理接口配置 GenC：映射启用、直接访问启用、平台角色为 `ADMIN`。
6. 调用 Genesis 管理接口配置 GenO：精确写入预检得到的同名外部用户 ID 和用户名，并开启直接访问。
7. 张涛 Genesis 登录转绿。

执行过程中曾因 PowerShell 使用 DTO 属性名 `active` 读取 JSON，而实际 JSON 字段为 `is_active`，触发一次安全停止。该停止发生在 Genesis 同步和平台写入之前；改用正确字段并确认其值为 `true` 后才继续。

### 5. 最终验收

| 用户名 | GenB | Genesis | GenC | GenO |
|---|---|---|---|---|
| `huanglinghu` | 启用、`ADMIN`、登录通过 | 启用、`ADMIN`、登录通过 | `ADMIN`、4 项权限、入口解锁 | 唯一同名启用 `admin`、精确映射、入口解锁 |
| `xuhaojian` | 启用、`ADMIN`、登录通过 | 启用、`ADMIN`、登录通过 | `ADMIN`、4 项权限、入口解锁 | 唯一同名启用 `admin`、精确映射、入口解锁 |
| `huzhengyao` | 启用、`ADMIN`、登录通过 | 启用、`ADMIN`、登录通过 | `ADMIN`、4 项权限、入口解锁 | 唯一同名启用 `admin`、精确映射、入口解锁 |
| `zhangtao` | 启用、`ADMIN`、登录通过 | 启用、`ADMIN`、登录通过 | `ADMIN`、4 项权限、入口解锁 | 唯一同名启用 `admin`、精确映射、入口解锁 |

最终管理接口验收为 4/4 通过。门户接口另行确认四人 GenC、GenO 入口均为 unlocked；平台角色、权限和外部映射以 Genesis 管理接口为准。

### 6. 代码与运维影响

- 本次只修改共享远程数据，不部署 JAR、前端、Nginx、GenC 或 GenO 服务。
- 不把具体人员固化到 `DataInitializer`，避免所有环境启动时自动创建真实人员账号。
- GenB 业务代码工作树保持干净；本报告与索引作为可追溯知识记录提交。
- 四人应在首次登录后按团队安全规范修改初始密码。
