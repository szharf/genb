# 核心记忆组件测试 Resources

## Knowledge

- [正式操作手册](../../operation/CORE_MEMORY_TESTBENCH_AND_TEST_AGENT_GUIDE.md)
  当前页面、凭证、短期/长期测试、CLI 智能体、证据和排障的完整权威操作说明。执行正式验收时使用。
- [核心记忆组件详细设计](../../design/GENB_CORE_MEMORY_COMPONENTS_DETAILED_DESIGN.md)
  五大系统、14 个核心组件和一期长短期记忆的设计边界。需要理解“为什么这样设计”时使用。
- [Control System 长短记忆开发指南](../../development/CONTROL_SYSTEM_MEMORY_IMPLEMENTATION_GUIDE.md)
  Control System 的接口、数据隔离、Redis/PostgreSQL、Worker 和安全规则。需要定位后端问题时使用。
- [核心组件平台开发总纲](../../development/CORE_COMPONENT_PLATFORM_DEVELOPMENT_GUIDE.md)
  GenB 控制面、执行面与智能体编排面的全局关系。需要理解组件注册、发布、绑定和调用时使用。
- [测试智能体 README](../../../../control-system-test-agent/README.md)
  当前薄 HTTP 测试智能体的运行方式和环境变量说明。运行 CLI 时使用。

## Wisdom (Communities)

- 项目内部：核心组件项目经理、Control System 开发负责人、GenB 开发负责人共同评审验收证据。
  系统行为高度依赖本项目当前契约和配置；对是否达到一期业务目标的判断应由三方基于同一份测试证据完成。

## Gaps

- 管理端已能生成/轮换长期服务凭证，但正式智能体部署到服务器后的 Secret 注入方式仍需部署规范。
- 当前测试智能体是执行后退出的 CLI，不提供常驻 HTTP 服务和健康检查。
- 当前本地 Runtime 使用确定性 Fake 结构化结果，只验证链路和契约，不证明真实模型质量。
