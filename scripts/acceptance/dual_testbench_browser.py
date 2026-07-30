import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("GENB_BROWSER_BASE_URL", "http://localhost:9100")
PASSWORD = os.environ["GENB_TEST_PASSWORD"]
OUTPUT = Path(os.getenv(
    "GENB_BROWSER_EVIDENCE",
    r"D:\code\opencode\genb\records\reports\assets\20260730-dual-testbench.png",
))


def choose(form_item, option_text: str) -> None:
    form_item.locator(".el-select").click()
    option = form_item.page.locator(".el-select-dropdown:visible .el-select-dropdown__item").filter(
        has_text=option_text
    )
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
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    login = page.request.post(
        "http://127.0.0.1:8581/api/v1/auth/login",
        data={"username": "admin", "password": PASSWORD},
    )
    token = login.json()["data"]["token"]
    page.add_init_script(f"localStorage.setItem('token', {json.dumps(token)})")

    page.goto(f"{BASE_URL}/genb/core-components/SHORT_TERM_MEMORY", wait_until="networkidle")
    page.wait_for_load_state("networkidle")
    if page.get_by_role("tab", name="独立测试台").count() == 0:
        raise RuntimeError(f"detail page missing test tab: url={page.url}; text={page.locator('body').inner_text()[:2000]}")
    page.get_by_role("tab", name="独立测试台").click()
    page.get_by_role("tab", name="管理员服务直测").click()

    service_form = page.locator(".service-test-form")
    implementation_item = service_form.locator(".el-form-item").filter(has_text="服务实现")
    choose(implementation_item, "standalone-short-term-memory-v1")
    config_item = service_form.locator(".el-form-item").filter(has_text="已发布配置")
    choose(config_item, "dual-testbench-default")
    task_item = service_form.locator(".el-form-item").filter(has_text="任务 ID")
    task_item.locator("input").fill("browser-direct-task-20260730")
    session_item = service_form.locator(".el-form-item").filter(has_text="测试会话 ID")
    session_item.locator("input").fill("browser-direct-session-1")
    message_item = service_form.locator(".el-form-item").filter(has_text="用户消息")
    message_item.locator("textarea").fill("浏览器管理员服务直测")
    page.get_by_role("button", name="直接测试组件服务").click()
    page.get_by_text("SERVICE_DIRECT", exact=True).wait_for(timeout=20_000)

    page.get_by_role("tab", name="智能体绑定测试").click()
    agent_form = page.locator(".test-form")
    agent_item = agent_form.locator(".el-form-item").filter(has_text="绑定智能体")
    choose(agent_item, "standalone-memory-test-agent")
    page.get_by_role("button", name="轮换服务凭证").click()
    page.locator(".el-message-box__btns .el-button--primary").click()
    page.get_by_text("新凭证只展示这一次", exact=False).wait_for(timeout=20_000)
    agent_task_item = agent_form.locator(".el-form-item").filter(has_text="任务 ID")
    agent_task_item.locator("input").fill("browser-agent-task-20260730")
    agent_session_item = agent_form.locator(".el-form-item").filter(has_text="测试会话 ID")
    agent_session_item.locator("input").fill("browser-agent-session-1")
    agent_message_item = agent_form.locator(".el-form-item").filter(has_text="用户消息")
    agent_message_item.locator("textarea").fill("浏览器智能体绑定测试")
    page.get_by_role("button", name="运行真实测试").click()
    page.get_by_text("AGENT_BINDING", exact=True).wait_for(timeout=20_000)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUTPUT), full_page=True)
    print(json.dumps({
        "url": page.url,
        "serviceDirectPassed": True,
        "agentBindingPassed": True,
        "consoleErrors": console_errors,
        "screenshot": str(OUTPUT),
    }, ensure_ascii=False))
    browser.close()
