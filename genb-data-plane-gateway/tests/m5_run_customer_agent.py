from __future__ import annotations

import os
import sys

import uvicorn


ROOT = r"D:\code\opencode\genb"
sys.path.insert(0, ROOT + r"\control-system-test-agent\src")
os.environ.update({
    "AGENT_ID":"core-component-demo-agent",
    "GENB_BASE_URL":"http://127.0.0.1:8581/api",
    "SERVICE_CREDENTIAL":"core-machine",
    "DATA_PLANE_GATEWAY_URL":"http://127.0.0.1:18080",
    "AGENT_REDIS_HOST":"127.0.0.1",
    "AGENT_REDIS_PORT":"16380",
    "AGENT_REDIS_PASSWORD":"",
})
uvicorn.run("control_system_test_agent.web:app", host="127.0.0.1", port=18714)
