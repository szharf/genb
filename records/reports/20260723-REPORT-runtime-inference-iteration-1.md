# Runtime Inference Iteration 1实施报告

## 1. 背景

核心组件平台已决定一期提前交付Runtime System最小Inference Engine，Direct Provider作为未来主路径、Alaya作为可选Adapter，Control System和智能体只依赖我方统一Interface。用户授权根据设计和开发文档制定详细任务计划并开始开发。

## 2. 目标

建立无需外部模型即可运行和验证的第一条纵向切片：公开HTTP Interface经过身份/scope、Inference深Module和Fake Provider Adapter返回统一结果，并覆盖结构化输出、Embedding、模型目录、健康和流式生命周期。

## 3. 范围

本次新增`runtime-system-service`独立Python工程、全项目实施计划、应用工厂、身份Port、Provider Port、Inference Module、Fake Adapter、受限JSON Schema校验、OpenAPI、配置Schema、README和Interface测试。

本次未调用真实模型、未写入凭证、未安装依赖、未修改GenB Java/Vue/数据库、未实现Control System、未部署生产。

## 4. 完成标准

- 服务可加载并在本地8704端口启动。
- 401/403使用统一Problem Details。
- 非流式、结构化、Embedding、models、live/ready、内部模型健康和SSE可用。
- Fake在生产环境不能使服务ready。
- Provider非法JSON和Embedding维度错误不会伪成功。
- OpenAPI、配置、测试和README完整。
- 无Runtime SDK依赖、秘密和外部网络调用。

## 5. 实施内容

1. 新建`runtime-system-service`，采用`src/runtime_system`布局和应用工厂。
2. 定义`IdentityVerifier`和`ModelProvider`两个Seam，分别由Static Token和Fake Model Adapter满足。
3. 实现`/inference`和统一`data/meta`响应。
4. 实现结构化输出；当前使用fail-closed JSON Schema子集，未知关键字拒绝。
5. 实现`/embeddings`及数量、顺序、维度、NaN/Infinity验证。
6. 实现逻辑模型目录，避免暴露secret、Endpoint和API key。
7. 实现SSE`started/delta/usage/completed`递增序列。
8. 实现live/ready和受scope保护的内部模型健康。
9. 生产环境使用Fake Provider时ready返回503。
10. 实现RFC 9457形态的认证、授权、请求和Provider错误；不回显敏感请求正文。
11. 新增OpenAPI 3.1 JSON、模型路由Schema、环境示例和README。

## 6. 当前进度

Iteration 1完成。下一迭代是M2 Provider选型验证和Direct Chat/Embedding Adapter；在Provider、凭证、费用和数据合规确认前，当前Fake实现不能作为生产模型能力。

## 7. 验收记录

- [x] pytest：15项通过。
- [x] `compileall`通过。
- [x] FastAPI应用导入成功，共7条业务/健康路径。
- [x] 短时启动`127.0.0.1:8704`，`/health/live`返回`{"status":"UP"}`，随后停止作业。
- [x] OpenAPI和路由配置JSON可解析。
- [x] 静态契约4条公开数据面路径，运行时包含7条业务/健康路径。
- [x] `bank_agent_runtime`、Alaya固定地址、硬编码API key/client secret扫描无命中。
- [x] `requests/httpx/aiohttp`导入扫描无命中，本轮无外部网络调用。
- [x] 未安装或下载依赖，因此无需更新安装下载记录。

## 8. 风险和遗留问题

- Static Token Adapter仅用于本地，生产JWT/mTLS/工作负载身份属于M2/M3。
- 模型目录当前是Iteration 1固定逻辑别名，后续由GenB发布配置替代。
- 受限JSON Schema Module只覆盖一期需要的关键字；完整Draft 2020-12需在依赖评审后以不改变外部Interface的方式替换。
- 尚未实现真实Provider、限流、重试、熔断、用量持久化和OpenTelemetry。
- 工作区有大量既有未跟踪文件和子仓库改动，提交必须严格精确暂存。
