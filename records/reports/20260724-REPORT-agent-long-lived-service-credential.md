# 智能体级长期服务凭证与页面闭环报告

## 1. 背景

原实现默认凭证90天、最长365天，并把组件scope固化到凭证；独立测试台只能粘贴凭证，不能生成。这会导致新增绑定需要重新签发、一个智能体出现多份凭证，并要求测试人员读取本地夹具文件，不符合产品目标。

## 2. 目标

每个智能体只维护一份当前有效的长期服务凭证。凭证只证明`agentId`机器身份；GenB根据用户权限和当前已启用绑定动态签发短期Actor Token。管理端提供生成、一次展示、复制、轮换、吊销和测试台自动填入。

## 3. 范围

- GenB凭证签发、认证、轮换、吊销、审计和组件会话。
- Control System双凭证验证职责调整。
- 管理端中英文凭证交互。
- 测试智能体短期/长期provisioning兼容。
- 远程开发PostgreSQL非破坏性迁移。

## 4. 完成标准

- 每个agent最多一条`ACTIVE`凭证，默认`expires_at=NULL`。
- 再次签发原子吊销旧凭证，明文仍只返回一次。
- 新增/停用组件绑定不要求轮换长期凭证。
- Control以服务凭证确认agent，以Actor Token确认用户、Session、组件和动作scope。
- 页面可以完成生成/轮换/复制并直接运行真实测试。

## 5. 实施内容

- `ServiceCredentialService`锁定agent并先轮换旧凭证，再生成唯一长期凭证。
- PostgreSQL增加`agent_id WHERE status='ACTIVE'`部分唯一索引。
- `ComponentSessionService`从已启用绑定动态生成组件动作scope。
- Control的`ActorIdentity`解析scope，执行动作时以Actor Token为授权依据。
- 新增`CoreComponentCredentialControl.vue`，测试表单按选中agent加载凭证状态。
- 更新provisioning脚本，移除同一agent的只读第二凭证和凭证固化scope。

## 6. 数据迁移

远程开发库迁移前后：

| 指标 | 迁移前 | 迁移后 |
|---|---:|---:|
| 凭证记录总数 | 67 | 67 |
| ACTIVE凭证 | 67 | 3 |
| ACTIVE仍有到期时间 | 67 | 0 |
| 存在多个ACTIVE的agent | 有 | 0 |

没有删除凭证记录。每个agent保留最新ACTIVE，其余标记`REVOKED`并保留审计历史。

## 7. 验收

- GenB凭证专项：12项通过。
- GenB完整后端：118项通过。
- Control System：52项通过，3项外部条件跳过。
- 管理端中文、英文构建通过；仅有既有大chunk警告。
- 真实浏览器：凭证状态、一次展示、自动填入、已绑定组件真实调用全部通过。
- 截图：`records/reports/assets/20260724-agent-service-credential-ui.png`。
- 本地服务：GenB、Control短期/长期依赖、Runtime均为`UP`。

## 8. 风险与后续

- 页面刷新后不能恢复旧凭证明文，这是只存哈希的安全边界；遗失时必须轮换。
- 当前单活轮换会让旧凭证立即失效，正式智能体轮换时必须同步更新Secret；如未来需要宽限期，应设计独立双槽状态。
- Actor Token由GenB/智能体代码自动换取，管理员不手工复制；后台无人值守任务还需后续定义`MACHINE_JOB` Actor。
