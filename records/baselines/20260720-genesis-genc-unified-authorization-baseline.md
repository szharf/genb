# Genesis / GenC 统一授权改造前基线

记录时间：2026-07-20 11:58（Asia/Shanghai）

本记录对应 `records/plans/20260720-PLAN-genesis-genc-unified-authorization.md` 的 Task 1。执行期间没有切换分支、暂存文件、提交代码、修改业务配置或写入数据库；所有既有未提交改动均保留原状。

## 1. Git 基线

### 1.1 根工作区

- 路径：`D:\code\opencode\genb`
- 分支：`main`
- HEAD：`6c0bdf6c8ae1170fa6afa83b9557a1469714a3f4`
- 最近提交：`2026-07-07T15:40:13+08:00 Update runtime and cli submodules`
- upstream：`origin/main`
- ahead / behind：`0 / 0`
- remote：
  - fetch：`https://github.com/szharf/genb.git`
  - push：`https://github.com/szharf/genb.git`
- 暂存区：无根工作区暂存改动。
- 工作区摘要：2 个普通文件修改、3 个子模块工作区变化、26 个未跟踪入口；合计 31 个 `git status --short` 入口。

```text
 M AGENTS.md
 M PROJECT_OVERVIEW.md
 M bank-agent-project/bank-agent-cli
 M bank-agent-project/bank-agent-runtime
 M gen-b
?? C01智能审单专家智能体/
?? CHANGELOG.md
?? CURRENT_TASKS.md
?? PROJECT_INDEX.md
?? ROADMAP.md
?? bank-agent-project/6bf0859ae3fc62e58535ba0cf899808b.png
?? bank-agent-project/780c3238fd93cd5dd3c4805bdc761359.png
?? bank-agent-project/9d68532469a91caaacc6a96fb74dc5cb.png
?? bank-agent-project/alaya_test.html
?? "bank-agent-project/bank-agent-cli - 副本/"
?? bank-agent-project/bank-agent-cli.rar
?? bank-agent-project/bank-agent-project.rar
?? bank-agent-project/docs/
?? bank-agent-project/examples/
?? bank-agent-project/scripts/
?? bank-agent-project/test_page.html
?? chat/
?? client-agents-my-response-20260630.json
?? context/
?? docs/
?? gen-c/
?? gen-o/
?? hs_err_pid16520.log
?? records/
?? replay_pid16520.log
?? video-frames-contact-sheet.jpg
```

### 1.2 GenB 工作区

- 路径：`D:\code\opencode\genb\gen-b`
- 分支：`codex/client-i18n-merge-20260715`
- HEAD：`70931f653b5b21740c51417b198a00bf353fe633`
- 最近提交：`2026-07-15T18:01:57+08:00 feat: complete client i18n and Genesis SSO integration`
- upstream：`company/client-i18n-merge-20260715`
- ahead / behind：`0 / 0`
- remotes：
  - `company`：`ssh://git@47.116.69.17:2424/huanglinghu/gen-b.git`
  - `origin`：`https://gitee.com/kdanotadc/gen-b.git`
- 暂存区：无暂存改动。
- 工作区摘要：11 个 Vite 依赖缓存文件修改、6 个 Vite 依赖缓存文件删除；合计 17 个 `git status --short` 入口。全部是执行 Task 1 前已经存在的改动。

```text
 M gen-b-console/node_modules/.vite/deps/@element-plus_icons-vue.js
 M gen-b-console/node_modules/.vite/deps/_metadata.json
 M gen-b-console/node_modules/.vite/deps/axios.js.map
 D gen-b-console/node_modules/.vite/deps/chunk-BXRPTJTD.js
 D gen-b-console/node_modules/.vite/deps/chunk-BXRPTJTD.js.map
 D gen-b-console/node_modules/.vite/deps/chunk-UC4PQXLF.js
 D gen-b-console/node_modules/.vite/deps/chunk-UC4PQXLF.js.map
 D gen-b-console/node_modules/.vite/deps/chunk-YFT6OQ5R.js
 D gen-b-console/node_modules/.vite/deps/chunk-YFT6OQ5R.js.map
 M gen-b-console/node_modules/.vite/deps/echarts.js.map
 M gen-b-console/node_modules/.vite/deps/element-plus.js
 M gen-b-console/node_modules/.vite/deps/element-plus.js.map
 M gen-b-console/node_modules/.vite/deps/pinia.js
 M gen-b-console/node_modules/.vite/deps/pinia.js.map
 M gen-b-console/node_modules/.vite/deps/vue-router.js
 M gen-b-console/node_modules/.vite/deps/vue-router.js.map
 M gen-b-console/node_modules/.vite/deps/vue.js
```

### 1.3 GenC 工作区

- 路径：`D:\code\opencode\genb\gen-c`
- 分支：`main`
- HEAD：`c855780bf13bdce9a88b1a0f529614cf322ae2ca`
- 最近提交：`2026-06-10T14:46:07+08:00 fix: 生产环境导出 Word/PPT 打到错误后端的问题`
- upstream：`origin/main`
- ahead / behind：`0 / 0`
- remote：
  - fetch：`ssh://git@47.116.69.17:2424/huzhengyao/agentAi.git`
  - push：`ssh://git@47.116.69.17:2424/huzhengyao/agentAi.git`
- 暂存区：`.env` 删除已被暂存，这是执行 Task 1 前已有状态，Task 1 未触碰 Git index。
- 工作区摘要：1 个已暂存删除、12 个未暂存修改、9 个未跟踪文件或目录；合计 22 个 `git status --short` 入口。

```text
D  .env
 M .gitignore
 M Front/.env.development
 M Front/.env.production
 M Front/src/api/index.ts
 M Front/src/router/index.ts
 M Front/src/store/index.ts
 M app.py
 M requirements.txt
 M routes/canvas_routes.py
 M routes/slot_routes.py
 M services/canvas/store.py
 M services/db.py
?? .env.example
?? Front/src/api/auth.ts
?? Front/src/composables/useAuthSession.ts
?? Front/src/views/AuthRequiredView.vue
?? Front/src/views/SsoCallbackView.vue
?? routes/auth_routes.py
?? services/auth_session.py
?? services/genesis_sso.py
?? tests/
```

未暂存 diff 统计：12 个已跟踪文件，新增 363 行、删除 103 行。暂存 diff 统计：`.env` 删除 6 行。未跟踪文件不计入 diff 行数。

## 2. 数据库基线

### 2.1 Genesis / GenB PostgreSQL

- 数据库类型：本机 PostgreSQL 18.1。
- 地址类别：local。
- 实际监听地址：`127.0.0.1:5432`。
- 数据库：`genb`。
- schema：`bank_agent_db`。
- 当前 schema 普通表数量：39。
- 运行后端：`D:\default\Codex\runtime\gen-b-console-local.jar`，端口 `8581`。
- 实际连接证据：Windows TCP 连接显示该 Java 进程连接 `127.0.0.1:5432`；`pg_stat_activity` 显示 5 个来自 `PostgreSQL JDBC Driver` 的 `genb` 本地连接。

注意：仓库 `application.yml` 和当前 JAR 内嵌配置仍写有远程 PostgreSQL 地址，但当前运行进程的实际 TCP 目的地及 PostgreSQL 会话均为本机。后续修改或重启前必须继续区分“文件默认配置”和“当前运行时实际连接”，不要根据仓库配置误操作远程库。本记录不包含数据库密码、ticket secret 或 token。

### 2.2 GenC SQLite

- 数据库类型：SQLite。
- 配置默认值：`GENC_DATABASE_PATH=slot_store.db`。
- 当前实际文件：`D:\code\opencode\genb\gen-c\slot_store.db`。
- 文件大小：61,440 字节。
- 源文件 SHA256：`23E2C63C7D6CBEC43EE8B34A7709BB8D98F14B598EFEF6404AFB69BF68F9E5A6`。
- 源库 `PRAGMA integrity_check`：`ok`。

## 3. 可恢复备份

备份目录：`D:\default\Documents\backups\genesis-genc-unified-authorization\20260720-task01`

### 3.1 PostgreSQL 自包含 custom archive

- 文件：`D:\default\Documents\backups\genesis-genc-unified-authorization\20260720-task01\genb-genb-bank_agent_db-20260720-115840.dump`
- 范围：`genb` 数据库的 `bank_agent_db` schema 及其数据。
- 格式：`pg_dump --format=custom`，不包含 owner 和 ACL。
- 大小：840,830 字节。
- SHA256：`8E907D1A53D1F1F03FF9C83FE94753855217663233440C20D15521AEBA133BD4`
- 验证：`pg_restore --list` 成功，归档目录包含 337 个条目。

恢复前应先停止会写入 Genesis 数据的后端，并再次备份当前状态。命令不包含密码；认证应通过交互或受保护的 `PGPASSFILE` 提供。

```powershell
$pgRestore = 'D:\JAVA\tool\pg\bin\pg_restore.exe'
$backup = 'D:\default\Documents\backups\genesis-genc-unified-authorization\20260720-task01\genb-genb-bank_agent_db-20260720-115840.dump'

# 先验证归档可读
& $pgRestore --list $backup

# 仅在明确回滚且已停止写入后执行；<local-user> 由本机安全配置提供
& $pgRestore `
  --host 127.0.0.1 `
  --port 5432 `
  --username '<local-user>' `
  --dbname genb `
  --clean `
  --if-exists `
  --no-owner `
  --no-privileges `
  $backup
```

首次备份尝试误用了仓库远程环境账号，认证失败并产生 0 字节临时文件；该无效文件已清理。上面带 SHA256 的 custom archive 是本任务唯一的 PostgreSQL 基线。

### 3.2 GenC SQLite 在线安全备份

- 文件：`D:\default\Documents\backups\genesis-genc-unified-authorization\20260720-task01\genc-slot-store-20260720-115553.sqlite3`
- 方式：Python 标准库 SQLite online backup API；源库以只读模式打开。
- 大小：61,440 字节。
- SHA256：`E4B47868EF082AC24A89A71D208763693BFE0229A75C407CFB44046AD953039A`
- 验证：源库和备份库分别执行 `PRAGMA integrity_check`，结果均为 `ok`。

SQLite online backup 会重新生成一致的数据库页，因此备份文件 SHA256 不要求与正在使用的源文件相同；完整性由 SQLite backup API 和源、目标两次 `integrity_check` 保证。

恢复前必须停止 GenC 后端，并先把当时的 `slot_store.db` 另行留档。

```powershell
$source = 'D:\default\Documents\backups\genesis-genc-unified-authorization\20260720-task01\genc-slot-store-20260720-115553.sqlite3'
$target = 'D:\code\opencode\genb\gen-c\slot_store.db'

# 确认 GenC 已停止后再执行
Copy-Item -LiteralPath $source -Destination $target -Force

# 恢复后校验
$env:GENC_RESTORE_PATH = $target
@'
import os, sqlite3
with sqlite3.connect(f"file:{os.environ['GENC_RESTORE_PATH']}?mode=ro", uri=True) as db:
    print(db.execute("PRAGMA integrity_check").fetchone()[0])
'@ | D:\JAVA\py\python.exe -
```

预期校验输出为 `ok`。

## 4. Task 1 验证结果

- [x] 三个工作区的分支、HEAD、remote、upstream、ahead / behind 已记录。
- [x] 三个工作区的 `git status --short` 基线已完整记录。
- [x] 用户已有的暂存、未暂存和未跟踪内容均未清理或覆盖。
- [x] GenB 当前运行时数据库已确认是本机 PostgreSQL `genb` / `bank_agent_db`，未把仓库远程默认配置误记为实际连接。
- [x] PostgreSQL custom archive 已生成，SHA256 与 `pg_restore --list` 证据齐全。
- [x] GenC 实际 SQLite 路径已确认，安全备份、SHA256 和完整性检查已完成。
- [x] 没有安装或下载任何工具，因此无需更新安装下载记录。
- [x] 没有修改数据库数据、业务代码、配置内容、Git 分支或 Git index。

Task 1 基线和可恢复备份已完成，可以在主任务审查通过后进入失败测试阶段。
