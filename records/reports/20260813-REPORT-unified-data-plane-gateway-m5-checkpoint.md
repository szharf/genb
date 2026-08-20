# 统一数据面网关M5阶段报告

- 日期：2026-08-13
结论：M5实现与大部分本地验收完成；Gate F未放行

## 1. 目标与边界

本轮按`20260812-PLAN-unified-data-plane-gateway-implementation.md`进入M5，完成本地总验收、兼容清单、性能资源门禁、容器交付和文档收口。只操作本地源码、回环端口、独立Redis和本地Docker；未连接、修改或部署服务器、生产数据库、生产Redis及生产Nginx。

## 2. 已完成实现

- 增加闭合环境变量运行工厂、`*_FILE`秘密注入、Redis AUTH、原子运行快照、默认Adapter Registry、健康检查和单worker启动入口。
- 增加非root容器与本地Compose样例；最终镜像使用`65532:65532`，约28 MB，并能在只读根文件系统下导入运行模块。
- Identity Token增加按主体的短时安全复用，保留最长60秒和到期前5秒刷新边界，解决20用户并发签名导致的延迟门禁失败。
- 18714在可信网关身份头存在时直接建立用户会话，不再二次进入旧SSO；退出统一改走网关注销入口。
- 增加20用户、20组件、20条SSE、500次调用内存增长、运行工厂启动失败/成功路径及真实Chrome脚本。
- 形成智能体兼容清单；对仅存在`user_id`字段但身份真源和存储隔离未经审计的对象明确标记`NEEDS_REVIEW`或`UNSUPPORTED_MULTI_USER`。

## 3. 自动化与浏览器证据

| 范围 | 最终结果 |
|---|---|
| 数据面网关 | 55 passed |
| 数据面合同 | 9 passed |
| 18714测试智能体 | 67 passed，1个第三方弃用告警 |
| GenB后端 | 169 passed，1 skipped，0 failure/error |
| GenB管理端 | Vite生产构建通过 |
| Python静态编译 | `compileall`通过 |
| Chrome安全链路 | 登录、刷新、Header清洗、SSE、退出后401通过 |
| Chrome三个体验 | 短期两轮、长期跨会话、Skill先澄清后生成、刷新恢复通过 |
| 完整确定性本地链路 | Nginx→数据面→18714→统一能力Interface→本地验收Adapter通过 |

浏览器截图保存在`genb-data-plane-gateway/artifacts/m5-browser/`。其中`m5_full_stack_browser.py`使用确定性本地Adapter，使结果不依赖外部模型和远程服务；它验证网关、页面和能力边界，但不等价于三个真实组件服务进程同时运行。

## 4. 性能与资源

- 20用户并发访问决策P95：7.596 ms，目标小于10 ms。
- 20组件并发能力调用P95：12.010 ms，目标小于50 ms。
- 20个并发SSE流均收到两个分块。
- 预热后500次能力调用的`tracemalloc`增长：7080 bytes，小于2 MiB门限。
- 镜像ID：`sha256:2c263d4f7c18f09b8b61be94b88f45d08fa226a77da93a1c856ece7cae92b50a`。

## 5. 安全与产物

- Docker Scout：31个包，0 Critical、0 High、0 Medium、0 Low。
- 生产源码Secret特征扫描通过；测试夹具中的本地假凭证不计为生产Secret。
- 只读容器、非root用户和Compose静态配置检查通过。
- SBOM：`genb-data-plane-gateway/artifacts/genb-data-plane-gateway-local-m5.spdx.json`，SHA-256 `2B3D5EA1DC1057CB9C6F4772DEE3A57CC2262F28BE951E72F29A491CE1E973B5`。
- CVE SARIF：`genb-data-plane-gateway/artifacts/genb-data-plane-gateway-local-m5.cves.sarif`，SHA-256 `025200B6B7FC193784D8F83A822236DB3CA0C6195515567EE574D47BAB058DAF`。
- Dockerfile SHA-256：`033ABB3243CD5CC69720B04716EB30D51EB65CF9BF68596AE0E99F7B5600B91E`。
- Compose SHA-256：`EFC446913832FBB5D0D3E711F04066C128565E6FA892DC58B77B593BFBFAF502`。

## 6. Gate F缺口

计划M5第1项要求在同一本地验收窗口实际运行Nginx、GenB、数据面、专用Redis、18714、三个组件和Fake外部服务。当前已经运行并验证Nginx、数据面、专用Redis、18714及Fake/确定性Adapter，也分别通过GenB和18714全量测试；但没有取得“GenB与短期记忆、长期记忆、规划推理三个真实服务进程同时经新数据面调用”的证据。

因此严格结论是：Gate F未通过，不能进入上线前检查计划，更不能部署。后续必须用本地Fake推理替代外部付费模型，启动真实GenB与三个组件服务，将数据面快照绑定到真实服务地址，再复跑两个用户、多会话、三个体验、刷新和退出矩阵。只有该证据通过，才能把本报告升级为完成报告并更新计划Gate F结论。

## 7. 工作树保护

根仓库和`gen-b`子仓库原本均存在用户及历史修改。本轮未执行reset、checkout、clean、批量格式化、提交或推送；最终仍需按文件审阅差异，不能把整个脏工作树视为本轮成果。
