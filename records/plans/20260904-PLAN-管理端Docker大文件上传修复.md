# 管理端 Docker 大文件上传修复计划

日期：2026-09-04

## 目标

让 GenB 管理端可以稳定上传大于 1 GiB、最大 5 GiB 的 Docker 文件，同时避免前端服务器完整缓存大文件、后端使用内存型 `/tmp` 暂存大文件，以及扩大其他接口的上传权限。

## 已确认基线

- `100 MiB` 请求可进入 Nginx 请求体接收阶段；`100 MiB + 1 byte` 稳定返回 HTTP 413。
- 前端 Nginx 有效配置为 `client_max_body_size 100m`。
- Spring multipart 上限为 5 GB，生产进程没有环境变量覆盖。
- 后端 `java.io.tmpdir=/tmp`，而 `/tmp` 是 7.6 GiB `tmpfs`；服务器当前无 Swap、可用内存约 2.3 GiB。
- 前端服务器可用磁盘约 5.7 GiB；后端 `/app` 可用约 45 GiB。
- 同事代码已经包含 `transferTo` 和“99% 等待服务端返回”的进度处理，本次不重复改写。

## 实施步骤与门禁

### M1：更新任务和配置基线

- 在 `CURRENT_TASKS.md` 登记任务、范围和验收标准。
- 在 Git Nginx 基线中为 `/genb/api/v1/deploy/upload` 增加精确 location。
- 只在该 location 设置 `client_max_body_size 5g`、一小时请求体/代理超时和 `proxy_request_buffering off`。
- 同步 IP 入口、两个官网域名共享路由和本地 Compose Nginx 基线。

验收：配置中普通 `/genb/api/` 仍继承 100 MiB，只有 Docker 上传精确路由允许 5 GiB。

### M2：迁移后端 multipart 临时目录

- 将 multipart 临时目录配置为可通过 `GENB_UPLOAD_TMP_DIR` 指定，默认使用应用目录下 `upload-tmp`。
- 生产创建 `/app/gen-b-console/upload-tmp`，权限只授予 GenB 运行用户。
- 在生产启动环境设置 `GENB_UPLOAD_TMP_DIR=/app/gen-b-console/upload-tmp`。

验收：目录位于 `/app` 所在磁盘，不再使用 `/tmp` 的 `tmpfs`；后端候选版本以 `ddl-auto=validate` 健康启动。

### M3：受控发布

- 备份前端 Nginx 主配置、共享路由和后端运行环境。
- 先上传配置到临时位置并执行 `nginx -t`，通过后原子替换并 reload。
- 构建并部署包含 multipart location 配置的新后端 JAR；失败自动恢复上一版。

验收：前后端健康均为 HTTP 200，生产 JAR校验值与本地一致。

### M4：边界与回归验收

- 重跑 `100 MiB + 1 byte`、`1 GiB + 1 byte` 的 `Expect: 100-continue` 探针，确认不再返回 413且探针不实际传输大文件。
- 验证超过 5 GiB 的声明请求仍返回 413。
- 回归 `/genb/`、`/portal/login`、`/genb/api/actuator/health`、GenC、GenO、FIBO 和两个官网首页。
- 检查 Nginx 临时目录没有残留探针文件，后端健康和磁盘水位稳定。

## 风险控制

- 不设置全局 5 GiB，防止其他项目和接口被动扩大攻击面。
- `proxy_request_buffering off` 后，客户端中断会直接终止上游流；需检查后端临时目录残留。
- 单文件上限仍为 5 GiB；当前不支持断点续传，网络中断需要重新上传。
- 不使用真实 Docker 镜像做自动探针，不触发镜像导入或容器启动。

## 回滚

1. 恢复本次备份的 Nginx 主配置和共享路由，执行 `nginx -t` 后 reload。
2. 恢复上一版 GenB JAR和启动环境，重启并验证 `8581/api/actuator/health`。
3. 保留 `upload-tmp` 目录，确认无运行中上传后再人工清理残留临时文件。

## 执行结果

- M1 至 M4 已于 2026-09-04 全部完成。
- 后端全量测试：180 项，失败 0，错误 0，跳过 1。
- 代码提交：`abc8edad 修复管理端Docker大文件上传链路`，已推送到远端现有 `shizhenhua` 分支。
- 前端 Nginx 只对 `/genb/api/v1/deploy/upload` 设置 `5g`、一小时超时和流式转发；普通 GenB API 仍保持 100 MiB 上限。
- 生产 multipart 临时目录已改为 `/app/gen-b-console/upload-tmp`，进程环境核验生效且目录无残留。
- 生产 JAR SHA256：`4e35edcbbbc5945788263e9ceae43fca4dae7dedd432c97aed5da2042c4becc8`。
- 前端配置备份：`/app/frontend-backups/genb/20260904_085825_large_upload`。
- 后端回滚备份：`/app/gen-b-console/backups/20260904_170025_large_upload`。
- 无文件体的边界探针结果：三个入口的 `1 GiB + 1 byte` 声明请求均已越过 Nginx 限制并到达后端；超过 5 GiB 返回 413；普通 API 的 `100 MiB + 1 byte` 返回 413。
- `/genb/`、`/genb-client/`、`/portal/login`、`/geno/`、`/journey/`、`/fibo/`、两个官网首页和 GenB 健康代理均返回 200。
- 本次未上传或导入真实 Docker 镜像，未部署或启动核心组件模型。
