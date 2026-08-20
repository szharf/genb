# GenB统一数据面网关M2完成报告

- 日期：2026-08-13
- 范围：仅本地统一访问纵向切片
结论：Gate C通过

## 完成交付

- 在`genb-data-plane-gateway`实现无框架ASGI网关、Gateway Session、Access Decision、RS256 Identity Token与JWKS。
- 提供内存测试Adapter、Redis RESP生产Adapter、GenB HTTP控制Adapter，以及无状态/身份读取两类Fake智能体。
- 增加本地Nginx `auth_request`配置，由Nginx直接代理JSON、SSE和WebSocket字节流。
- 增加GenB机器身份`POST /api/v1/internal/data-plane/identity/revoke`，按agent原子撤销session grant；控制OpenAPI同步闭合Schema。
- Nginx关闭浏览器请求Header整体下沉，按业务allowlist和鉴权结果重建Header，网关Cookie不进入智能体。

## 安全验收

- Cookie：`HttpOnly`、`SameSite=Lax`、`Path=/agents`，本地HTTP关闭Secure，生产配置默认开启。
- 登录：state绑定agent与同agent相对returnPath并单次消费；code由唯一机器身份交换。
- 退出/过期/撤权：本地会话立即失败关闭，控制面grant原子撤销且重放401。
- 路由：上游只允许精确命中发布allowlist；拒绝metadata地址、跨agent跳转、路径穿越和双重编码。
- Header：浏览器伪造身份、上游、转发和任意`X-GenB-*`不能到达智能体；浏览器响应不含真实上游和内部Token。
- 隔离：Alice只能访问agent-a，Bob只能访问agent-b；Alice Cookie访问agent-b返回401。

## 验证证据

- M2 Python：12项通过，含真实Nginx、独立16380 Redis、SSE和WebSocket。
- GenB Java全量：167项通过、0失败、1项既有Redis Testcontainers条件跳过。
- 数据面合同：7项通过。
- Python `compileall`：通过。
- Nginx 1.31.3：`nginx -t`通过；官方包位于D盘且下载/安装记录含SHA-256。

## 边界与下一步

本轮未操作服务器、生产Nginx、生产Redis、生产数据库或容器。路由与授权使用Fake发布表完成Gate C纵切；M4再接完整快照缓存、主动失效与轮询。下一步只能进入M3 Capability Invocation、Adapter Registry、Secret Resolver和统一错误，不得提前进入服务器治理或生产部署。
