# GenB核心组件控制面Iteration 3阶段报告

日期：2026-07-23

## 1. 结论

已在GenB后端完成M3第一条可运行控制面闭环：管理员通过现有登录和JWT查询固定五系统/14组件目录，注册Component Implementation，创建并发布配置版本，将专用测试智能体绑定到已发布版本，并解析当前生效主绑定。

本轮只使用H2测试数据库，没有连接或修改远程PostgreSQL，没有开发Vue页面，也没有调用Runtime System。

## 2. 数据Module

新增`core_systems`、`core_components`、`component_implementations`、`component_config_versions`和`agent_component_bindings`五类JPA对象。固定目录由幂等Initializer维护；核心系统和核心组件没有新增Interface，管理员只能注册Implementation、配置和绑定。

## 3. 管理Interface

- `GET /v1/core-components`
- `POST /v1/core-components/{componentCode}/implementations`
- `POST /v1/core-components/{componentCode}/configs`
- `POST /v1/core-components/{componentCode}/configs/{configId}:publish`
- `POST /v1/core-components/{componentCode}/bindings`
- `GET /v1/core-components/{componentCode}/bindings/agents/{agentId}`

Controller只负责协议和当前Actor映射，目录、注册、状态机、秘密检查和绑定约束集中在`CoreComponentControlService`深Module。

## 4. 权限与安全

- 核心组件路径由Spring Security强制`authenticated`。
- 读、配置和绑定分别使用`component.read`、`component.configure`、`component.bind`。
- 三项权限幂等授予GenB现有`ADMIN`角色，普通用户没有默认权限。
- 配置JSON递归拒绝`password/apiKey/clientSecret/token/secret/secretRef`等秘密字段。
- secret只允许通过独立`secretRefs`字段保存引用；本轮没有凭证明文生成或展示。
- 重复主绑定返回409；非法对象关系和草稿绑定返回400。

## 5. 自动化验证

新增7项端到端集成行为，全部经过真实默认管理员/普通用户登录、JWT过滤器、方法权限、Controller、Module和H2 JPA：目录读取、Implementation注册、配置发布、绑定解析、重复绑定冲突、身份权限拒绝、秘密和草稿绑定拒绝。

GenB后端全量结果：13份测试报告，89项测试，0失败、0错误、0跳过。

## 6. 未完成项

- 当前项目仍依赖Hibernate `ddl-auto:update`；生产需要显式迁移及回滚方案。
- 尚未拆出Interface Registry、Endpoint Registry、Config Schema和审计表。
- 尚未实现Implementation启停、配置列表/回滚、绑定停用/解绑和灰度影子绑定。
- 尚未实现服务凭证、组件会话、过期/吊销、scope和Runtime侧绑定校验。
- 尚未实现健康快照、测试运行、审计检索和Runtime注册握手。
- 尚未开发14张组件卡、配置/绑定页面和独立测试台。
- 生产配置中的数据库/JWT秘密外置不属于本轮，部署前必须单独处理。
