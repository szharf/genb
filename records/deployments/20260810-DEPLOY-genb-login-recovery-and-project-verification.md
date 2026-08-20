# GenB 登录恢复与三项目线上验证记录

日期：2026-08-10

## 范围

- 前端服务器：`16.162.33.130`
- 后端服务器：`47.116.69.17`
- GenB 目录：`/app/gen-b-console`
- Nginx 配置：`/etc/nginx/conf.d/alaya-to.conf`（只读核对，未修改或 reload）

## 变更

本次没有上传或替换部署包。仅执行运行恢复：

1. 清理后端服务器归档 systemd 日志和 DNF 缓存。
2. 使用现有 `stop.sh`、`start.sh` 重启 GenB 后端。
3. 删除 3 个无容器引用的 Docker 悬空镜像。

没有修改数据库、Nginx、GenC、GenO 容器或业务数据。

## 验收

| 项目 | 验证入口 | 结果 |
|---|---|---|
| Genesis | `/portal/login` | 200，约 0.16 秒 |
| 统一登录 | `/genb-client/api/v1/genesis/auth/login` | 浏览器真实登录 200 |
| GenB | `/genb/`、`/genb-client/`、`/genb/api/actuator/health` | 200 |
| GenC | `/journey/`、`/journey-api/health` | 200 |
| GenO | `/geno/`、`47.116.69.17:7200/openapi.json` | 200 |
| GenO reasoning | `47.116.69.17:7201/actuator/health` | 200 |

连续三轮健康回归均通过。

## 回滚

- 没有代码或配置替换，因此没有部署包回滚项。
- GenB 如再次异常，先检查磁盘和 `/app/gen-b-console/log/app.log`，再使用现有 `stop.sh`、`start.sh` 精确重启。
- 已删除的归档日志、DNF 缓存和悬空镜像不在服务器保留；悬空镜像可通过重新构建恢复。

## 风险

后端根分区仍为 `98%`。本次恢复了服务，但尚未完成业务归属明确的深度磁盘清理。
