import json
import os
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


PASSWORD = os.environ["GENB_TEST_PASSWORD"]
START_SCRIPT = Path(r"D:\code\opencode\genb\scripts\start_standalone_memory_test_agent.ps1")


def choose(form_item, option_text: str) -> None:
    form_item.locator(".el-select").click()
    option = form_item.page.locator(
        ".el-select-dropdown:visible .el-select-dropdown__item"
    ).filter(has_text=option_text)
    option.first.click()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        executable_path=os.getenv(
            "GENB_BROWSER_EXECUTABLE",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ),
    )
    page = browser.new_page(viewport={"width": 1600, "height": 1100})
    login = page.request.post(
        "http://127.0.0.1:8581/api/v1/auth/login",
        data={"username": "admin", "password": PASSWORD},
    )
    token = login.json()["data"]["token"]
    page.goto("http://localhost:9100/portal/login", wait_until="networkidle")
    page.evaluate("token => localStorage.setItem('token', token)", token)
    page.goto(
        "http://localhost:9100/genb/core-components/SHORT_TERM_MEMORY",
        wait_until="networkidle",
    )
    page.get_by_role("tab", name="独立测试台").click()
    page.get_by_role("tab", name="智能体绑定测试").click()
    form = page.locator(".test-form")
    choose(
        form.locator(".el-form-item").filter(has_text="绑定智能体"),
        "standalone-memory-test-agent",
    )
    page.get_by_role("button", name="轮换服务凭证").click()
    page.locator(".el-message-box__btns .el-button--primary").click()
    page.get_by_text("新凭证只展示这一次", exact=False).wait_for(timeout=20_000)
    credential_input = form.locator("input[autocomplete='new-password']")
    credential = credential_input.input_value()
    if not credential:
        raise RuntimeError("issued credential was not filled into the test form")
    timestamp = int(time.time())
    form.locator(".el-form-item").filter(has_text="任务 ID").locator("input").fill(
        f"credential-browser-task-{timestamp}"
    )
    form.locator(".el-form-item").filter(has_text="测试会话 ID").locator("input").fill(
        f"credential-browser-session-{timestamp}"
    )
    form.locator(".el-form-item").filter(has_text="用户消息").locator("textarea").fill(
        "验证调用后凭证仍然保留"
    )
    page.get_by_role("button", name="运行真实测试").click()
    page.get_by_text("AGENT_BINDING", exact=True).wait_for(timeout=20_000)
    retained = credential_input.input_value() == credential
    stored = page.evaluate(
        """agentId => {
          const values = JSON.parse(localStorage.getItem('genb.coreComponentTest.credentials.v1') || '{}')
          return Boolean(values[agentId])
        }""",
        "standalone-memory-test-agent",
    )
    page.reload(wait_until="networkidle")
    page.get_by_role("tab", name="独立测试台").click()
    page.get_by_role("tab", name="智能体绑定测试").click()
    form = page.locator(".test-form")
    choose(
        form.locator(".el-form-item").filter(has_text="绑定智能体"),
        "standalone-memory-test-agent",
    )
    reloaded = form.locator("input[autocomplete='new-password']").input_value() == credential
    browser.close()

environment = os.environ.copy()
environment["SERVICE_CREDENTIAL"] = credential
completed = subprocess.run(
    [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(START_SCRIPT),
        "-Password",
        PASSWORD,
        "-CredentialFromEnvironment",
    ],
    env=environment,
    check=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(json.dumps({
    "credentialAutoFilled": True,
    "credentialRetainedAfterCall": retained,
    "credentialStoredByAgent": stored,
    "credentialReloadedAfterRefresh": reloaded,
    "agentRestartedWithSameCredential": completed.returncode == 0,
}, ensure_ascii=False))
