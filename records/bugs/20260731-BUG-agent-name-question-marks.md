# 测试智能体中文名称显示为问号

## 现象

智能体列表中的 `standalone-planning-test-agent` 和 `core-component-demo-agent` 名称、描述或分类显示为 `???`。

## 根因

两个 PowerShell 启动脚本先用 `ConvertTo-Json` 生成包含中文的字符串，再交给 `Invoke-RestMethod`，但没有明确按 UTF-8 字节发送。Windows PowerShell 采用了不匹配的请求编码，问号已经写入 PostgreSQL，因此不是浏览器字体或前端渲染问题。

## 修复

- `start_planning_integration_local.ps1` 和 `start_customer_core_agent_local.ps1` 统一使用 `application/json; charset=utf-8`，并显式发送 UTF-8 字节。
- 启动脚本在智能体已存在时也刷新中文名称、描述、分类和运行地址，避免错误历史数据长期保留。
- 当前本地库中的两条智能体数据已修复为正常中文。

## 验证

- GenB 客户端智能体接口返回两条正确中文名称，不再包含 `???`。
- PowerShell 脚本语法检查通过。
- 中文终端若显示为形如 `æ ¸å¿` 的字符，是终端响应解码显示差异；数据库直接查询结果为正确中文，与本问题不同。
