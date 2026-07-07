# Gen-B 目录清理建议

更新时间：2026-07-07

本文只说明哪些文件/目录可以删除、删除影响是什么，不代表已经删除。

## 结论

当前需要长期保留的项目只有 5 个：

1. `bank-agent-project\bank-agent-cli`
2. `bank-agent-project\bank-agent-runtime`
3. `gen-b\gen-b-backend`
4. `gen-b\gen-b-client`
5. `gen-b\gen-b-console`

其他目录大多不是主项目。它们可以按用途分为：

- 缓存/构建产物：可删，影响小，可重新生成。
- 部署产物/镜像包：可删，但会影响回滚、重部署和问题追溯。
- 智能体来源材料：可删，但会影响后续维护某些智能体。
- 历史文档/截图/接口快照：可删，不影响运行，但会损失历史记录。

## 不能删除

这些不要删除，否则会直接影响当前主项目开发或代码管理。

| 路径 | 原因 |
|---|---|
| `AGENTS.md` | 当前工作规则。 |
| `PROJECT_OVERVIEW.md` | 当前项目说明文档。 |
| `CLEANUP_GUIDE.md` | 当前清理说明文档。 |
| `bank-agent-project\bank-agent-cli` | 智能体 CLI 主项目。 |
| `bank-agent-project\bank-agent-runtime` | 智能体 Runtime/SDK 主项目。 |
| `gen-b\.git` | `gen-b` 正式代码仓库的 Git 元数据。 |
| `gen-b\.gitignore` | `gen-b` 正式仓库忽略规则。 |
| `gen-b\gen-b-backend` | Gen-B 后端主项目。 |
| `gen-b\gen-b-client` | Gen-B 客户端主项目。 |
| `gen-b\gen-b-console` | Gen-B 管理端主项目。 |

注意：`gen-b-backend`、`gen-b-client`、`gen-b-console` 目录整体不能删，但这些项目内部的构建产物可以删，见后文。

## 可以删除，影响小

这些一般是缓存、日志、截图、接口快照或可重新生成的构建产物。删除后最多需要重新安装依赖、重新构建或重新运行测试。

| 路径 | 删除影响 |
|---|---|
| `.git` | 当前根目录下这个 `.git` 不是有效 Git 仓库，Git 不识别；删除影响小。 |
| `.npm-cache` | npm 缓存；删除后 npm 可能重新下载依赖。 |
| `.trae` | IDE 配置；不用 Trae 时可删。 |
| `logs` | 本地运行日志；删除不影响项目运行。 |
| `browser-login-before.png` | 浏览器验证截图；删除只损失历史截图。 |
| `browser-my-agents-admin-20260630.png` | 浏览器验证截图；删除只损失历史截图。 |
| `browser-my-agents-filtered-20260630.png` | 浏览器验证截图；删除只损失历史截图。 |
| `client-agents-my-response-20260630.json` | 接口响应快照；删除只损失历史排查记录。 |
| `gen-b\start-test.log` | 测试启动日志；删除不影响运行。 |
| `gen-b\gen-b-backend\target` | Maven 构建产物；删除后可通过 `mvn package` 重新生成。 |
| `gen-b\gen-b-client\dist` | 客户端构建产物；删除后可通过 `npm run build` 重新生成。 |
| `gen-b\gen-b-client\.vite` | Vite 缓存；删除后会自动重建。 |
| `gen-b\gen-b-client\node_modules` | 前端依赖；删除后需要重新 `npm install`。 |
| `gen-b\gen-b-client\test-results` | 浏览器测试结果；删除只损失测试截图/报告。 |
| `gen-b\gen-b-console\dist` | 管理端构建产物；删除后可通过 `npm run build` 重新生成。 |
| `gen-b\gen-b-console\node_modules` | 前端依赖；删除后需要重新 `npm install`。 |
| `gen-b\gen-b-console\node_modules\.vite` | Vite 依赖缓存；删除后会自动重建。 |
| `bank-agent-project\bank-agent-cli\bank_agent_cli.egg-info` | Python 包安装元数据；可重新生成。 |
| `bank-agent-project\bank-agent-cli\bank_agent_cli\__pycache__` | Python 缓存；可自动重建。 |
| `bank-agent-project\bank-agent-runtime\.pytest_cache` | pytest 缓存；可自动重建。 |
| `bank-agent-project\bank-agent-runtime\bank_agent_runtime\__pycache__` | Python 缓存；可自动重建。 |

## 可以删除，但有影响

这些不影响 5 个主项目的代码启动，但会影响部署回滚、智能体重建、历史追溯或资料复用。建议删除前先确认不再需要。

| 路径 | 删除影响 |
|---|---|
| `deploy-artifacts` | 本地部署包、jar、tar.gz、Docker 镜像包；删除后本地无法直接回滚或重新上传这些版本。 |
| `agent-docker-images` | 本地 Docker 镜像归档；删除后需要重新构建或重新从服务器取。 |
| `agent-docker-contexts` | 智能体 Docker 构建上下文；删除后对应智能体镜像不方便重建。 |
| `agent-builds` | 智能体构建/改造工作区；删除后会丢失部分智能体改造源和中间结果。 |
| `agent-intake` | 用户上传智能体后的接入整理区；删除后会丢失接入过程材料。 |
| `C01智能审单专家智能体` | 智能审单专家独立源项目、测试数据、报告；删除不影响 Gen-B 平台前后端代码，但影响该智能体后续维护。 |
| `chat` | 历史设计文档、SDK 文档、阶段报告和导出记录；删除不影响运行，但影响追溯。 |
| `test_exports` | 早期 SDK 导出包验证；删除不影响主项目，但影响历史验证。 |
| `test_exports_v2` | SDK v2 导出包验证；删除不影响主项目，但影响历史验证。 |
| `test_stage3` | 阶段测试目录；删除不影响当前主项目。 |
| `test_stage4` | 阶段测试目录；删除不影响当前主项目。 |
| `test_stage5` | 阶段测试目录；删除不影响当前主项目。 |
| `test_stage6_2` | 阶段测试目录；删除不影响当前主项目。 |
| `test_stage6_3` | 阶段测试目录；删除不影响当前主项目。 |
| `70旅程agent_extracted.txt` | 70 旅程资料提取结果；删除后会丢失分类来源依据。 |
| `agent_business_categories_from_pdf.json` | 智能体业务分类映射资料；删除后会丢失分类追溯文件。 |
| `bank-agent-project\docs` | PRD、安装、Docker、代码审查文档；删除不影响包运行，但影响项目理解。 |
| `bank-agent-project\examples` | 示例材料；删除不影响主项目，但影响学习和测试。 |
| `bank-agent-project\scripts` | 辅助脚本；删除前需确认没有正在使用。 |
| `bank-agent-project\bank-agent-cli - 副本` | CLI 备份副本；删除前确认与正式 `bank-agent-cli` 无差异需求。 |
| `bank-agent-project\*.rar` | 压缩归档；删除后失去原始打包备份。 |
| `bank-agent-project\*.png` | 资料图片；删除只影响资料查看。 |
| `bank-agent-project\*.html` | 测试/演示页面；删除只影响历史测试页面。 |
| `gen-b\client-prototype` | 客户端 UI 原型；删除不影响当前客户端代码，但影响设计回溯。 |
| `gen-b\hello_agent` | 示例智能体；删除不影响平台主线，但影响示例验证。 |
| `gen-b\*.md` | 需求、任务、数据库字段等文档；删除不影响运行，但影响理解和追溯。 |
| `gen-b\*.conf` | Nginx 配置样例；删除不影响本地代码，但影响部署参考。 |
| `gen-b\start-backend.cmd` | 本地启动脚本；删除后少一个快捷启动入口。 |
| `gen-b\start-client.cmd` | 本地启动脚本；删除后少一个快捷启动入口。 |

## 不建议单独删除的项目内部源码

这些在 5 个主项目内，属于源码或配置。除非明确重构，不要按清理动作删除。

| 路径 | 原因 |
|---|---|
| `bank-agent-project\bank-agent-cli\bank_agent_cli` | CLI 源码。 |
| `bank-agent-project\bank-agent-cli\pyproject.toml` | CLI 包配置。 |
| `bank-agent-project\bank-agent-cli\README.md` | CLI 说明。 |
| `bank-agent-project\bank-agent-cli\AGENT_STANDARD.md` | 智能体标准说明。 |
| `bank-agent-project\bank-agent-runtime\bank_agent_runtime` | Runtime/SDK 源码。 |
| `bank-agent-project\bank-agent-runtime\tests` | Runtime 测试。 |
| `bank-agent-project\bank-agent-runtime\pyproject.toml` | Runtime 包配置。 |
| `bank-agent-project\bank-agent-runtime\README.md` | Runtime 说明。 |
| `gen-b\gen-b-backend\src` | 后端源码。 |
| `gen-b\gen-b-backend\pom.xml` | Maven 配置。 |
| `gen-b\gen-b-backend\db` | 数据库脚本。 |
| `gen-b\gen-b-backend\cli` | 后端生成/管理的智能体示例或运行材料；删除前需确认后端相关功能不依赖。 |
| `gen-b\gen-b-backend\docker-files` | 后端本地 Docker 文件材料；删除前需确认不影响本地部署测试。 |
| `gen-b\gen-b-client\src` | 客户端源码。 |
| `gen-b\gen-b-client\package.json` | 客户端依赖和脚本。 |
| `gen-b\gen-b-client\vite.config.ts` | 客户端构建配置。 |
| `gen-b\gen-b-client\tests` | 客户端测试。 |
| `gen-b\gen-b-console\src` | 管理端源码。 |
| `gen-b\gen-b-console\package.json` | 管理端依赖和脚本。 |
| `gen-b\gen-b-console\vite.config.js` | 管理端构建配置。 |

## 推荐清理顺序

1. 先删影响小的缓存和构建产物：`target`、`dist`、`.vite`、`node_modules`、`__pycache__`、`.pytest_cache`、日志、截图。
2. 再评估部署产物：`deploy-artifacts`、`agent-docker-images`。如果近期可能回滚，不删。
3. 再评估智能体材料：`agent-builds`、`agent-docker-contexts`、`agent-intake`、`C01智能审单专家智能体`。如果还要维护对应智能体，不删。
4. 最后再评估历史资料：`chat`、`test_exports*`、`test_stage*`、旧文档、旧配置样例。

## 建议

真正要清理前，建议先移动到一个临时归档目录，例如 `D:\code\opencode\genb_cleanup_backup_20260707`，确认项目能启动、能构建、能访问后，再永久删除。
