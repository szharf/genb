# 生产就绪检查 M0 只读报告

- 日期：2026-08-13
- 范围：`47.116.69.17`、`16.162.33.130` 的系统级资源与 GenB/Genesis 白名单资产
结论：Gate A 通过；Gate B 未通过，等待用户逐项批准 M1 治理

## 1. 边界

未停止或重启服务，未修改 Nginx、Docker、Redis、数据库、应用文件或生产配置；未枚举其他项目目录、现有 Redis Key、其他容器内容或 Docker 数据目录。为计算历史 JAR 汇总，检测命令曾创建并在同一命令内删除一个 `/tmp/genb_m0_jars.<pid>` 临时文件；服务器未留下该文件，也没有持久化业务状态变更。

## 2. 系统资源快照

| 项目 | 前端 `16.162.33.130` | 后端 `47.116.69.17` |
|---|---:|---:|
| CPU | 2 核，load 0.00/0.00/0.00 | 4 核，load 0.00/0.03/0.07 |
| 内存 | 916 MiB，总可用 432 MiB | 15 GiB，总可用 5.2 GiB |
| Swap | 0 | 0 |
| 根分区 | 8.0 GiB，已用 55%，可用 3.7 GiB | 99 GiB，已用 93%，可用 7.0 GiB |
| 根分区 inode | 2% | 11% |

网络接口计数无 error/drop。前端只监听 80；后端 8581 正常监听。准备使用的 `/app/genb-data-plane/`、`genb-data-plane` Docker 网络、`genb-data-plane-gateway` 与 `genb-data-plane-redis` 均不存在，不与既有同名资产冲突。

## 3. GenB 后端白名单

- `/app/gen-b-console/` 总占用 4.2 GiB；当前 JAR 为 `gen-b-console-1.0.0.jar`，2026-08-06，SHA-256 `7aaca4c2b4c66fc0d11801ba757e55935eb0bfdf4752707cb813b332782592a3`。
- GenB Java PID 1852025，已运行约 3 天，RSS 约 659 MiB；`/api/actuator/health` 返回 `UP`。
- 25 个历史 JAR 共 1,656,078,324 bytes。保留按 mtime 最新两份后，23 个更旧候选共 1,522,893,929 bytes。
- 应保留的最新两份为 `gen-b-console-1.0.0.jar.bak.20260722_175315_genc_role_permissions` 和 `gen-b-console-1.0.0.jar.bak.20260721_153402_before_login_perf`；两者均已取得 SHA-256。
- 三个 GenB 日志文件共 26,480,174 bytes；5 秒采样均未增长。当前没有项目专用轮转证据。
- 目录中的智能体上传 TAR/CLI 内容未作为清理候选，也未继续展开检查，因为其可能属于其他智能体资产。

## 4. 前端白名单

- `/ayala/genb` 6.3 MiB、`/ayala/genb-client` 6.5 MiB、`/ayala/genb-en` 6.3 MiB、`/ayala/genb-client-en` 1.8 MiB；当前四个 `index.html` 均已取 SHA-256。
- 部署记录中列出的 10 个历史静态备份目录当前均不存在，因此没有可批准的前端备份删除目标。
- `/etc/nginx/conf.d/alaya-to.conf` 存在，SHA-256 `6f1c1bfdd5ca7fc6f281f83b5f8eb3daab5aee555a2de9a94e0b1ce6b1df6778`；部署记录中的一个 GenB 配置备份当前不存在。
- 只读核对确认 `/genb`、`/genb-en`、`/genb-client`、`/genb-client-en` 与 `/portal/login` 路由仍指向上述白名单目录或后端 8581。
- 公网只读请求中，统一登录页、四个中英文前端和 GenB 健康接口均返回 200。

## 5. 失败基线与放行判断

后端根分区从前次 92% 恶化到 93%，仅余 7.0 GiB，明显不满足 Gate B 的“低于 80% 且至少 20 GiB 可用”。即使删除全部 23 个已归属旧 JAR，最多只释放约 1.42 GiB，仍无法达到容量水位。因此：

- Gate A：通过。白名单证据、潜在 JAR 候选、保留版本、哈希和恢复方向已明确。
- Gate B：未通过。M1 需用户逐项批准；白名单治理后仍必须申请系统盘扩容，禁止扩大到其他项目或 Docker/Redis 资产清理。
- 生产部署：继续禁止。

## 6. 待批准动作

1. 在保留当前 JAR 与上述最新两份备份的前提下，删除 23 个更旧 JAR 候选；恢复方式为保留备份或按对应 Git 版本重新构建并校验哈希。
2. 为三个 GenB 应用日志增加项目专用 logrotate 规则；先保存规则副本并验证，不清空活动日志、不修改全局日志策略。
3. 完成白名单治理复核后，为后端系统盘创建云快照，并基于实际分区/文件系统提交扩容操作；该不可逆容量操作需要再次单独批准。
