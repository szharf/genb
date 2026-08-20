# 进入M5前核心组件收敛完成报告

- 日期：2026-08-06
范围：仅本地代码、本地服务和本地PostgreSQL；未操作服务器及服务器数据库。

## 结论

进入M5前的两项债务已经关闭：GenB支持同一Implementation安全向上升版；短期记忆多个公共真源已通过公开控制面Interface原子收敛。三个核心组件的最终绑定解析和运行接口一致性通过，可以开始M5总验收，但本报告不把M5本身标记为完成。

## 实现结果

- `POST /api/v1/core-components/manifests:import`允许同一Implementation仅向严格更高的`x.y.z`版本升级；运行地址、健康地址、runtime和Adapter必须不变，同版本重复、降级或参数漂移失败关闭。
- 新增`POST /api/v1/core-components/{componentCode}/implementations:converge`。接口对该组件Implementation和绑定加悲观写锁，在一个事务内验证完整旧真源集合、目标PUBLISHED配置和稳定code，迁移启用绑定、停用旧实现并记录审计。
- 自动化先证明少报一个旧实现时返回409且绑定不变，再证明完整列举后迁移成功。
- 短期记忆和规划的完整接口采用新版本，不覆盖历史1.0.0契约。规划1.1.0发布后，一致性检查发现静态OpenAPI少一个运行时路由，因此保留1.1.0并发布修正后的1.1.1。

## 本地数据库最终状态

| 组件 | 唯一REGISTERED实现 | Interface | 配置/绑定 |
| --- | --- | --- | --- |
| SHORT_TERM_MEMORY | `short-term-memory-service-v1`，ID 4，18705 | 1.1.0 | 5个ENABLED/PRIMARY绑定全部使用PUBLISHED配置ID 6；旧实现ID 1、2为DISABLED |
| LONG_TERM_MEMORY | `long-term-memory-service-v1`，18702 | 1.0.0 | 三组件会话解析到配置ID 10 |
| PLANNING_REASONING | `planning-reasoning-service-v1`，ID 5，18712 | 1.1.1 | 原2个绑定保留；三组件会话解析到配置ID 7 |

验收使用的临时服务凭据均已撤销。

## 一致性与回归

- 18705：`/version`、运行时OpenAPI、静态OpenAPI和Manifest均为1.1.0；运行时/静态路由集合6/6一致。
- 18712：四者均为1.1.1；运行时/静态路由集合15/15一致。
- 8581真实三组件会话返回18705/config 6、18702/config 10、18712/config 7。
- 18714 `/health/live`为UP；测试智能体63项全量通过。
- GenB Java相关5个测试类共35项通过。
- 规划服务40项通过、4项因外部环境条件跳过。
- 短期记忆11项通过、1项因外部环境条件跳过。
- Manifest/OpenAPI静态合同2项通过。

## M5入口判断

前置条件已满足。M5仍需按计划完成三组件自然语言浏览器验收、秘密扫描、旧9100入口删除和最终Gate F记录；演示冻结期间继续禁止操作服务器及服务器数据库。
