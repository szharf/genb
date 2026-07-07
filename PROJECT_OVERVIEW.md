# Gen-B 项目说明

更新时间：2026-07-07

当前 `D:\code\opencode\genb` 下需要作为“项目”记录和维护的只有 5 个：

1. `bank-agent-project\bank-agent-cli`
2. `bank-agent-project\bank-agent-runtime`
3. `gen-b\gen-b-backend`
4. `gen-b\gen-b-client`
5. `gen-b\gen-b-console`

其他目录多数是输入材料、历史文档、测试产物、部署产物、缓存或智能体构建中间目录，不应作为主项目入口维护。

## 五个项目

| 项目 | 路径 | 技术栈 | 定位 |
|---|---|---|---|
| 智能体 CLI | `D:\code\opencode\genb\bank-agent-project\bank-agent-cli` | Python | 智能体脚手架/生成器，根据 spec 和模板生成标准智能体项目。 |
| 智能体 Runtime/SDK | `D:\code\opencode\genb\bank-agent-project\bank-agent-runtime` | Python | 智能体运行时底座，提供 Agent 基类、运行上下文、LLM、记忆、工具、策略、安全、审计、观测和算子 SDK。 |
| Gen-B 后端 | `D:\code\opencode\genb\gen-b\gen-b-backend` | Java 17、Spring Boot、PostgreSQL | 统一后端服务，负责登录、用户、角色、权限、智能体管理、授权申请、审批、部署和运行状态。 |
| Gen-B 客户端 | `D:\code\opencode\genb\gen-b\gen-b-client` | Vue 3、Vite、TypeScript、Pinia、Element Plus | 业务用户门户，包含我的智能体、智能体市场、我的申请、个人中心和审批入口。 |
| Gen-B 管理端 | `D:\code\opencode\genb\gen-b\gen-b-console` | Vue 3、Vite、Pinia、Element Plus、ECharts | 管理端/运维管控前端，包含驾驶舱、算子中心、智能体中心、监控运维、本体治理和系统管理。 |

## 项目关系

```text
bank-agent-cli
    生成智能体项目模板
    生成出的智能体代码依赖 bank-agent-runtime

bank-agent-runtime
    提供智能体运行 SDK
    被生成智能体或示例智能体 import 使用

gen-b-backend
    提供统一 API 和数据库访问
    可调用 bank-agent CLI 命令生成/管理智能体
    管理智能体部署、元数据、授权和状态

gen-b-client
    调用 gen-b-backend API
    面向业务用户使用智能体和申请权限

gen-b-console
    调用 gen-b-backend API
    面向管理员/运维管理智能体、算子、监控和系统配置
```

## 调用关系说明

### `bank-agent-cli`

`bank-agent-cli` 是生成器，不是平台运行服务。

它主要做这些事：

- 读取智能体 spec。
- 根据 `templates/default` 渲染智能体项目。
- 生成的智能体代码会 import `bank_agent_runtime`。
- `operator_sdk` 目录通常是对 `bank_agent_runtime.operator_sdk` 的桥接层。

它不依赖 `gen-b-client`、`gen-b-console`。

### `bank-agent-runtime`

`bank-agent-runtime` 是 Python SDK/运行时。

它主要提供：

- `BaseEmployeeAgent`
- `create_agent_app`
- memory、llm、tools、policy、reasoning、observability、operator_sdk 等模块
- Alaya Gateway 适配能力

它不依赖 `gen-b-client`、`gen-b-console`，也不是 Java 后端编译依赖。

### `gen-b-backend`

`gen-b-backend` 是 Gen-B 平台核心后端。

它直接管理：

- 用户、角色、权限
- 智能体元数据
- 智能体授权
- 智能体申请审批
- 智能体部署记录
- Docker / Python 智能体运行状态

它和 `bank-agent-cli`、`bank-agent-runtime` 的关系是：

- 后端代码里有 `CliController`，会检查或调用 `bank-agent` CLI 命令。
- 后端资源配置里有 `cli.sdk-source`，指向 Runtime/SDK 源路径。
- 后端 `cli` 目录下有生成出来的智能体示例，这些 Python 智能体会 import `bank_agent_runtime`。
- 但 Java 后端本身不是通过 Maven 依赖 `bank-agent-runtime`；Runtime 是智能体运行侧依赖。

### `gen-b-client`

`gen-b-client` 是业务客户端前端。

它只应该调用 `gen-b-backend` API，不直接调用：

- `bank-agent-cli`
- `bank-agent-runtime`
- `agent-builds`
- `agent-docker-contexts`
- `deploy-artifacts`

主要页面：

- 登录
- 我的智能体
- 智能体市场
- 我的申请
- 个人中心
- 审批页

### `gen-b-console`

`gen-b-console` 是管理端前端。

它只应该调用 `gen-b-backend` API，不直接调用：

- `bank-agent-cli`
- `bank-agent-runtime`
- `agent-builds`
- `agent-docker-contexts`
- `deploy-artifacts`

主要页面：

- 总览驾驶舱
- 算子中心
- 智能体中心
- 监控运维中心
- 本体治理中心
- 系统管理

## 其他目录的定位

下面这些目录不应作为主项目记录，只需在需要时按用途查阅：

| 目录/文件 | 定位 |
|---|---|
| `agent-builds` | 智能体构建/改造工作区，属于中间材料。 |
| `agent-docker-contexts` | Docker 镜像构建上下文，属于打包材料。 |
| `agent-docker-images` | Docker 镜像归档，属于部署产物。 |
| `agent-intake` | 用户上传智能体后的接入整理区。 |
| `deploy-artifacts` | 前端压缩包、后端 jar、镜像 tar 等部署产物。 |
| `logs` | 本地运行日志。 |
| `chat` | 历史对话、阶段文档、SDK 文档沉淀。 |
| `C01智能审单专家智能体` | 独立智能体源项目/测试数据/报告，可作为智能体来源，但不是 Gen-B 平台主项目。 |
| `test_exports*`、`test_stage*` | SDK/CLI/运行时阶段测试和导出验证目录。 |
| `.npm-cache`、`node_modules`、`.vite`、`target`、`dist` | 缓存或构建产物，不是源码项目。 |
| `70旅程agent_extracted.txt`、`agent_business_categories_from_pdf.json` | 智能体分类资料和提取结果。 |
| `browser-*.png`、`client-agents-my-response-*.json` | 验证截图和接口快照。 |

## 维护原则

- 平台功能修改优先看 `gen-b-backend`、`gen-b-client`、`gen-b-console`。
- 智能体生成规范修改看 `bank-agent-cli`。
- 智能体运行能力修改看 `bank-agent-runtime`。
- 不要把 `agent-builds`、`agent-docker-contexts`、`deploy-artifacts` 当成长期源码项目。
- 部署包、缓存、日志、截图、接口快照原则上不提交。
- 涉及服务器、数据库、Nginx、Docker 的操作必须先确认当前是否处于演示或生产冻结期。

## 推荐阅读顺序

1. `D:\code\opencode\genb\PROJECT_OVERVIEW.md`
2. `D:\code\opencode\genb\AGENTS.md`
3. `D:\code\opencode\genb\gen-b\gen-b-backend`
4. `D:\code\opencode\genb\gen-b\gen-b-client`
5. `D:\code\opencode\genb\gen-b\gen-b-console`
6. `D:\code\opencode\genb\bank-agent-project\bank-agent-cli`
7. `D:\code\opencode\genb\bank-agent-project\bank-agent-runtime`
