# Runtime Inference Iteration 2阶段报告

日期：2026-07-23

## 1. 结论

已完成M2的离线工程主链路：Runtime System可以从版本化JSON配置加载OpenAI-compatible Direct Provider，将逻辑模型别名路由到真实Provider模型，并通过既有Inference Interface提供普通推理、结构化输出、SSE流式和Embedding。测试全部使用`httpx.MockTransport`替换真正的外部HTTP Seam，没有联网、真实密钥或付费调用。

本报告不宣称M2整体验收完成。真实Provider选型、官方契约、脱敏调用、费用、地域和数据政策仍是生产前门禁。

## 2. 交付内容

- 新增`runtime_system.routing`深Module，集中承担配置验证、Secret解析、路由、协议转换和错误归一。
- 新增OpenAI-compatible Direct Provider Adapter。
- 运行入口支持`MODEL_ROUTING_CONFIG`绝对路径。
- `secretRef`一期只允许`env://VARIABLE_NAME`，真实值不进入配置文件。
- `/models`改为由当前Provider发布目录，不再硬编码在HTTP层。
- Provider结果携带真实或估算用量标记；Fake保持估算，Direct使用Provider用量。
- 新增路由JSON Schema和无秘密示例配置。

## 3. 已验证行为

- 逻辑别名普通推理与usage/finish reason归一。
- JSON Schema发送到Provider并在Runtime返回前二次校验。
- Embedding保持输入顺序，校验数量、维度和有限值。
- SSE读取`data:`事件并转换为Runtime标准事件。
- 流式上游故障以唯一`response.error`终止，不产生伪`completed`事件。
- 429→`MODEL_RATE_LIMITED`。
- Provider 5xx/401/403/连接失败→`MODEL_PROVIDER_UNAVAILABLE`。
- 超时→`MODEL_TIMEOUT`。
- 非法Provider响应→`MODEL_PROVIDER_BAD_RESPONSE`。
- 未发布别名或能力不匹配fail-closed。
- 未发布Embedding维度在访问Provider前被拒绝。
- 重复`modelAlias`、重复`providerId`、未知`providerId`、非HTTP(S)地址和缺失环境Secret在启动前失败。
- 错误响应不包含Provider原始正文。

## 4. 安全边界

- Adapter只持有进程内解析后的secret，不通过返回模型、目录或错误暴露。
- `baseUrl`只允许HTTP(S)，且禁止URL内嵌用户名和密码。
- 配置Pydantic模型使用`extra=forbid`，未知字段不会被静默接受。
- 测试token仅为合成值，未写入真实API Key。
- 本轮未添加日志输出，因此不会记录Prompt、响应或Authorization头。

## 5. 测试结果

- `pytest`：32项通过。
- `compileall`：通过。
- OpenAPI、路由Schema和示例JSON解析：通过。
- 敏感模式与日志调用扫描：未发现真实秘密或正文日志。

## 6. 未完成项

- 尚未选择并批准真实Chat/Embedding Provider及具体模型。
- 尚未用脱敏数据执行官方契约和真实网络联调。
- 尚未完成费用、配额、地域、训练/保留/删除政策评审。
- 尚未实现一次可控重试、熔断、Fallback、主动Provider健康探测和OpenTelemetry。
- `env://`是本地/初始部署Adapter，生产需替换为Secrets Manager或工作负载身份Adapter。
- GenB配置发布、RBAC、审计和绑定属于M3。
