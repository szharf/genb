# Long-term Memory Iteration 13实施与验收报告

日期：2026-07-24

## 结果

Control System已交付Long-term Memory一期纵向切片，并贯通GenB控制面、管理测试台、测试智能体、Runtime Inference Interface、远程PostgreSQL和本机Redis。M5与M6一期范围完成；完整RAG仍属于M13，不在本轮冒充完成。

## 实现

- 公开Interface：提取任务、任务状态、检索和幂等软删除。
- Store：PostgreSQL Repository Adapter，所有读写携带tenant/user/agent完整scope；精确去重、置信度更新、保留期和删除审计。
- Worker：PENDING/RUNNING租约、过期租约恢复、指数退避、最大尝试次数、DEAD、NO_WRITE和结构化输出校验。
- 安全：提交前脱敏、候选二次敏感过滤、三类允许记忆、配置阈值、服务凭证与Actor Token双身份。
- GenB：长期记忆真实测试运行器、提取状态/写入/拒绝/召回结果展示，中英文页面均构建通过。
- 测试智能体：长期记忆提取、状态、跨会话检索和软删除客户端；单代码通过agentId与凭证隔离A/B实例。

## 数据库

远程开发schema `bank_agent_db`幂等创建4张表：`long_term_memories`、`memory_extraction_jobs`、`memory_extraction_events`、`memory_audit_events`。实际物理外键数量为0。验收数据使用`iteration13-*`隔离标识追加；删除验收只执行业务软删除，没有物理删除既有业务数据。

## 验收证据

- Control System：远程PostgreSQL与真实Redis组合回归通过；PostgreSQL合同、无外键、作用域和软删除均自动验证。
- Runtime System：35项测试通过；本地结构化Fake夹具在production明确拒绝启动。
- GenB后端：全量测试通过；长期记忆Invoker专项和组件访问集成测试通过。
- Test Agent：9项测试通过。
- GenB Console：7个Node测试入口通过；中文、英文生产构建通过，只有既有chunk体积警告。
- 浏览器：长期记忆详情页、独立测试台、一次性凭证提示、绑定选择和用户消息表单真实渲染，控制台0错误。截图保存在`D:\default\Documents\genb_iteration13_long_term_testbench.png`。
- 四段链路：`GenB -> Control System -> Runtime Inference -> PostgreSQL`结果为`SUCCEEDED`；跨session召回至少1条，Agent B命中0条，敏感原文回显0，软删除成功，未绑定智能体拒绝。
- 临时18581/18701/18704进程全部停止；现有8581保持运行；一次性凭证文件已删除。

## 发现并修复的问题

- 临时GenB缺少租户与Actor Token密钥时正确fail-closed；验收使用仅限本地的临时RSA密钥和显式租户。
- `GENB_BASE_URL`必须是主机根地址；内部路径已包含`/api`。带`/api`会形成`/api/api/...`并导致双身份校验401。
- Windows上临时Java进程可能在父进程对象退出后仍占端口；验收按明确端口、启动时间和PID二次清理，未触碰现有服务。

## 未关闭门禁

- M2真实Provider的费用、数据政策和真实结构化/Embedding调用门禁未关闭。
- M7生产容量、监控告警、灰度、备份恢复和正式密钥轮换演练尚未完成。
- M8—M14其余11组件、完整RAG和五系统总验收尚未开始实现。
