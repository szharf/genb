# Python 项目启动 500 修复与 FIBO 恢复

日期：2026-09-10。状态：平台修复已部署，用户原实例已在 18 启动并通过本机 HTTP 健康检查。

## 实际结果

- 智能体 `agent-1789008009749`，实例 `7783d566-69db-4371-827b-12ab69d5c5c1`，node18，端口 18001。
- 使用用户原上传材料和原实例 ID 修复，不新建重复实例，不修改本地 FIBO 源码或原 ZIP。
- systemd active/running、NRestarts=0；首页 HTTP 200；pip check 无依赖冲突。
- 实测内存 50,524,160 字节（约 48 MiB），运行 MemoryMax=201,326,592 字节（192 MiB）。
- 远端实际 RUNNING/health=true 后，将原失败实例、任务状态核对为 HEALTHY，并同步该智能体运行状态。三个更新均各影响一行；修改前保存记录备份，版本号递增。
- 尚未发布网关入口，没有执行 LLM 调用、Fuseki 初始化或完整业务流程。首页可用不代表业务依赖全部验收。

## 发布内容和回滚点

- 47 正式 JAR：`/app/gen-b-console/gen-b-console-1.0.0.jar`，SHA256 `dbbc7deb565ddc4e684115294dcd4049c662dc0d584de498243b112e9438797e`。
- JAR 发布目录：`/app/gen-b-console/releases/zip-start-20260910/`；备份：`/app/gen-b-console/backups/zip-start-20260910/`，上一版 SHA256 `526a0493bf043245d8eff8178cbeee7d2d07ceee9f50e2f88b55e42bcd2df333`。
- 两节点 `/usr/local/libexec/genb-node/` 更新 ZIP 根目录识别、startable 检查及 pip --no-compile。
- `genb_node.py` SHA256：`ee1be2fc453d29212e07f5db091395ba49e8aeb4ec12938657572c94f65db55a`。
- `node_service.py` SHA256：`45c13cedd49bdf782c97fb142e14df645f1b1a8e7e933f74edb7b58364b200d5`。
- 47 原节点脚本：本次后端备份目录的 `node/`；18 原脚本：`/var/backups/genb-zip-start-20260910/`。
- 原 18 失败目录完整保存在 `/var/backups/genb-zip-start-20260910/7783d566-69db-4371-827b-12ab69d5c5c1/`。恢复前确认缺少 work 和 systemd unit，只移动此已核验实例目录。
- 数据库核对前的实例和任务记录：47 本次备份目录 `instance-before-reconcile.json`，权限 600。
- 没有修改 Nginx、前端、数据库结构；保留原 FIBO 隧道和既有站点。

后端代码回滚使用原 stop/start 脚本和本次备份 JAR。节点代码回滚恢复各自备份脚本。恢复原失败目录或数据库记录前必须先停止这个实例并核对当前状态，不能覆盖正在运行的应用；失败现场仅用于追溯，不建议回滚已恢复实例。

## 低内存依赖安装处理

owlready2 0.51 源码的构建依赖与元数据生成在 18 的 192/256 MiB 限制下均触发过 OOM。未取消节点内存保护。47 使用专用无登录用户 `genb-wheel-builder`、隔离 venv、768 MiB/1 CPU 的受限临时 systemd 任务准备 wheel；源码通过 PyPI 官方元数据 SHA256 验证，构建依赖为 setuptools/wheel/Cython/packaging。生成 wheel SHA256 为 `ac569815d073087c99895a2feecd1fe464da8067d8e7c77a81bd56986afde1fa`。

wheel 通过已有 47→18 受限节点上传通道传输并再次核对大小与 SHA256，保存于实例 `work/wheels/`。18 恢复安装使用该 wheel、256 MiB 临时安装任务和 --no-compile，pip check 通过；运行服务仍是原 192 MiB。内存不足、旧 setuptools 元数据校验、中转不完整包的失败日志均保留，最终只使用校验一致的完整 wheel。

这是本次原实例的运维辅助恢复，**平台尚未实现通用的自动跨节点依赖构建**。未来全新部署同样较重的项目，仍应准备与目标 Python/系统兼容的 wheel/锁定依赖，并评估安装与运行资源。安装下载位置记录在 `D:/default/Documents/install_download_log.md`。

## 验证

后端 206 项，0 失败、1 跳过；节点 8 项通过。临时 18581 校验后切换正式服务，正式健康 UP。四套 GenB、GenO、原 FIBO 页面/status 均 200，前两轮跨域修复的公网回归通过。根因见 `../bugs/20260910-BUG-Python项目目录包装与未完成部署启动500.md`。
