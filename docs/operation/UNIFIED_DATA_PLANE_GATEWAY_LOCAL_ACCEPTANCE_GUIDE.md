# 统一数据面网关本地验收指南

- 日期：2026-08-13
范围：M5 Gate F本地验收；禁止直接照搬为生产部署步骤

## 验收入口

- 网关应用：`127.0.0.1:18080`（M2/M5本地夹具）或容器`127.0.0.1:9080`。
- Nginx统一入口：`http://127.0.0.1:18081/agents/{agentId}/`。
- 18714体验智能体：只作为Nginx上游，浏览器不直接使用其端口。
- 本地专用Redis：`127.0.0.1:16380`，不得复用生产Redis。

## 自动验收

```powershell
Set-Location D:\code\opencode\genb\genb-data-plane-gateway
$env:GENB_REDIS_E2E='1'
$env:GENB_NGINX_E2E='1'
python -m pytest tests --ignore=tests/test_m0_security_red.py -q
python tests\m5_full_stack_browser.py
```

浏览器脚本应依次完成：

1. 统一入口登录后直接进入18714，不出现第二次智能体登录。
2. 短期记忆连续两轮后显示“验证完成”。
3. 长期偏好写入后新建真实对话，跨会话检索显示“验证完成”。
4. Skill先返回澄清问题，补齐材料后生成Skill。
5. 页面刷新后保留对话；退出后再次访问返回401。
6. Chrome控制台无非预期错误，响应不显示上游地址、Secret或Actor Token。

截图保存在`genb-data-plane-gateway/artifacts/m5-browser/`。

注意：仓库内`m5_full_stack_browser.py`的三个能力由确定性本地验收Adapter提供，用于稳定验证统一入口、18714、能力调用信封和页面状态，不会调用外部付费模型。它不是三个真实组件服务进程同时运行的替代证据。Gate F还必须另行启动本地GenB、短期记忆、长期记忆、规划推理和Fake推理服务，把发布快照指向这些真实组件进程，并重复上述浏览器矩阵。

## 容器与安全门禁

```powershell
docker build -t genb-data-plane-gateway:local-m5 .
docker scout sbom local://genb-data-plane-gateway:local-m5 --format spdx `
  --output artifacts\genb-data-plane-gateway-local-m5.spdx.json
docker scout cves local://genb-data-plane-gateway:local-m5 `
  --only-severity critical,high --exit-code --format sarif `
  --output artifacts\genb-data-plane-gateway-local-m5.cves.sarif
```

通过条件：镜像用户为`65532:65532`，Compose为只读根文件系统、1CPU/1GiB，Critical/High扫描退出码为0。任何高危命中都必须修复或形成明确阻塞，不得只保存报告后放行。

## 人工点击核对

1. 打开统一入口，观察地址栏始终为网关地址。
2. 开发者工具检查Cookie：只有不透明Gateway Session，`HttpOnly + SameSite=Lax`。
3. Network中搜索`token`、`secret`、`upstream`，不得看到Actor Token、服务Secret或真实组件地址。
4. 分别刷新三个场景，确认对话历史恢复。
5. 点击退出，再打开原URL，必须得到401或重新登录，不得继续显示旧用户数据。

## Gate F判定

只有自动化、容器安全、兼容清单和“真实GenB + 三个真实组件进程”的浏览器矩阵全部通过，才能标记Gate F通过。当前2026-08-13检查点仅完成前者与确定性Adapter浏览器链路；真实组件同窗证据缺失，因此不得进入上线前检查计划。

## 停止与清理

只停止本轮精确启动的Nginx、网关夹具、18714和16380 Redis进程。不得按名称批量停止其他Redis、Java、Python或Nginx进程；Docker镜像保留用于复核，生产部署另走上线前检查计划。
