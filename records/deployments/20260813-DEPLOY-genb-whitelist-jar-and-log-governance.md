# GenB 白名单历史 JAR 与日志治理记录

- 日期：2026-08-13
- 服务器：`47.116.69.17`
授权：用户已明确批准生产就绪计划 M1 的旧 JAR 治理和 GenB 项目专用 logrotate

## 边界与运行基线

- 仅操作 `/app/gen-b-console/` 中下列 23 个精确历史 JAR，以及 `/etc/logrotate.d/genb-console`。
- 不进入或修改其他项目目录、`docker-files/`、`cli/`、Docker、Redis、数据库、Nginx和其他日志规则。
- 8581 对应 PID 1852025，工作目录 `/app/gen-b-console`，运行命令 `java -jar gen-b-console-1.0.0.jar`。
- 当前运行 JAR 禁止删除；按 mtime 最新的两份回滚 JAR禁止删除。
- 删除前总候选大小：1,522,893,929 bytes。

## 保留产物

- 当前：`/app/gen-b-console/gen-b-console-1.0.0.jar`，SHA-256 `7aaca4c2b4c66fc0d11801ba757e55935eb0bfdf4752707cb813b332782592a3`。
- 回滚1：`/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260722_175315_genc_role_permissions`。
- 回滚2：`/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260721_153402_before_login_perf`。

## 获批删除清单

| 大小（bytes） | SHA-256 | 文件 |
|---:|---|---|
| 66545146 | `c3a6d482e5350f23ee8cbb87099b6c0e795077677de67463cf0384f9cf0af6bb` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260721_100627_before_08e2b5e` |
| 66410775 | `f499779023e3b8139ba3b14d4752cdcd8005895cc3e2f01363cce0f20c62be73` | `/app/gen-b-console/backups/gen-b-console-1.0.0.jar.20260709182310` |
| 66409930 | `dc02286fcc8f0367d54e22feecef0964ec592ff16f8d50d76f7ca3c5b9f7164c` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260703_100240_catalog_timeout` |
| 66409735 | `7f9ce7fa78e2c9ff844f9ce9fd199a2c87b2fbfbbaf4b9a7ccefa65e72921a79` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260701_1245_agent_status_normalize` |
| 66409930 | `dc02286fcc8f0367d54e22feecef0964ec592ff16f8d50d76f7ca3c5b9f7164c` | `/app/gen-b-console/gen-b-console-1.0.0-20260701_1245_agent_status_normalize.jar` |
| 66408543 | `95af09cb36d184250ddb80c6513686a628c6a151588f6c31cddbf494819b9f38` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260701_112430_sync_colleague` |
| 66402868 | `659a9fe948381b3c5619f754d5ab89c0421a97245a300a366ffb9748f3cf8c04` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260701_105106_business_attribute` |
| 66405629 | `e4854ab672872aa7f43a1354e168d231ce9918d70b73a50028c2db05129ecdcd` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260630_104250_revert_client_visible` |
| 66405538 | `deb32882ae4df8f9594184a900f54fc38170e1f7529c3ff4b18399bfd9a00447` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260630_102724` |
| 66405398 | `77e4d1a386d09097332c125d943f396136855ce23fb0bfdc2098133b83c30345` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_172611.retry` |
| 66338944 | `8af9f33042572bf8b032bb76d9751bce2b49a55910968bd0c76a1cbf19b8cc61` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_172208` |
| 66405555 | `c91d128271b182370363537531a6805c61370b987ac3d5c666b9e1afd310ce8c` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_151954` |
| 66405025 | `9f33a8316e809ce2deeffc76a88c06e2fbf5edb56e08e8438ab22c9b6609baad` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_143627` |
| 66404650 | `3a30764bbe6368c648d7320fb1f53e79e5c14c953d5acbee8ed92a38aec8d171` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_142743` |
| 66404350 | `5f20e47df65df804f399b859935b9fc0408c74c2bd840b716f74aba069198d87` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_141803` |
| 66403989 | `b15fbac87d926f376f67cfaab6271433380b6073a4f95b18dd2d84db10a2dbcc` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_141427` |
| 66402748 | `2c91ee6710f255a44806daade475d5d5376f5f6aabf61c3b971926c5ddaf6124` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_141051` |
| 66402740 | `93625a44b69384d9b45c3a97dce3bb9027872fdb05c8c363fd2f446926b498dc` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_130154` |
| 66402811 | `1d18a5f1ee4b46307b341264a52f1c696941be27709efaad2470d309d973552a` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_140121` |
| 66401843 | `b3c53d715a9bc3bb821b029f8574e991c41676593e1b632e90313a992ca1e8e9` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_125817` |
| 66398259 | `1e1bfd8f64649cfdd54eb83c5e0617803d4b0f176d6b7201fa7139de5e845dac` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_125436` |
| 66336409 | `aa6914159e845908887728bdc8864e9d7eb55ed367d32cf2c0fa1ebdb41fb0e3` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak.20260629_113258` |
| 61973114 | `53b074b0938bb3d97490bb60e2605f9fcc551e0e48464c10d6f40a6a76329041` | `/app/gen-b-console/gen-b-console-1.0.0.jar.bak` |

## 日志规则设计

仅覆盖以下三个文件：

- `/app/gen-b-console/log/app.log`
- `/app/gen-b-console/logs/gen-b-console-.log`
- `/app/gen-b-console/app.log`

计划采用 `daily`、`maxsize 100M`、`rotate 7`、`compress`、`delaycompress`、`missingok`、`notifempty`、`copytruncate`。安装前执行语法检查和隔离副本强制轮转演练；不重启 GenB，不修改全局 logrotate 配置。

## 恢复方式

- 当前和两份保留 JAR可直接用于回滚；更早版本需要从对应 Git 版本重新构建，并与本记录哈希核对。
- logrotate 规则可删除或恢复为安装前状态（安装前不存在）；已生成的压缩日志可解压读取。

## 执行结果

- 删除前两次尝试均因本地记录中人工抄录的单条 SHA-256 不一致而在预检阶段退出；删除循环尚未开始，服务器文件未发生部分删除。修正记录后，23 条路径、哈希和总大小全部一致才进入删除阶段。
- 已逐文件删除 23 个获批历史 JAR，释放 1,522,893,929 bytes。删除不可直接从服务器回收；更早版本需按本记录从对应 Git 版本重建并校验哈希。
- `/app/gen-b-console` 从 4.2 GiB 降至 2.8 GiB；根分区从 93%/可用7.0GiB改善到91%/可用8.7GiB，仍不满足Gate B。
- 最终目录中只剩当前 JAR和两份获批保留回滚 JAR；三者哈希均已复核。
- `/etc/logrotate.d/genb-console` 已安装，属主权限 `root:root 0644`，SHA-256 `2604d1428a5c88c82e77357c9ea047a03066bc0abecb48a624bb408cc3dbe61b`。
- 使用三个日志的隔离副本完成强制 `copytruncate` 演练，原文件被原地截短且 `.1` 归档完整；生产日志没有被强制轮转。
- 安装规则通过 `logrotate -d` 解析；GenB PID始终为1852025，未重启，健康为`UP`。
- 统一登录、GenB管理端、GenB客户端和代理后的健康接口最终均返回200。
