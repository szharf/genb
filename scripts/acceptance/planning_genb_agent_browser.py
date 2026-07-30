import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("GENB_BROWSER_BASE_URL", "http://localhost:9100")
PASSWORD = os.environ["GENB_TEST_PASSWORD"]
CREDENTIAL = os.environ["GENB_PLANNING_CREDENTIAL"]
ASSET_DIR = Path(r"D:\code\opencode\genb\records\reports\assets")


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
    console_errors: list[str] = []
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )
    login = page.request.post(
        "http://127.0.0.1:8581/api/v1/auth/login",
        data={"username": "admin", "password": PASSWORD},
    )
    token = login.json()["data"]["token"]
    page.goto(f"{BASE_URL}/portal/login", wait_until="networkidle")
    page.evaluate(
        """([token, credential]) => {
          localStorage.setItem('token', token)
          localStorage.setItem('genb-client-token', token)
          localStorage.setItem(
            'genb.coreComponentTest.credentials.v1',
            JSON.stringify({'standalone-planning-test-agent': credential})
          )
        }""",
        [token, CREDENTIAL],
    )

    page.goto(
        f"{BASE_URL}/genb/core-components/PLANNING_REASONING",
        wait_until="networkidle",
    )
    page.get_by_role("tab", name="独立测试台").click()
    page.get_by_role("tab", name="管理员服务直测").click()
    direct_form = page.locator(".planning-test").first
    choose(
        direct_form.locator(".el-form-item").filter(has_text="服务实现"),
        "planning-reasoning-service-v1",
    )
    choose(
        direct_form.locator(".el-form-item").filter(has_text="已发布配置"),
        "default",
    )
    direct_form.get_by_role("button", name="调用规划与推理服务").click()
    page.locator(".test-result__planning").filter(has_text="NEEDS_CLARIFICATION").wait_for(timeout=20_000)
    direct_ok = True

    page.get_by_role("tab", name="智能体绑定测试").click()
    agent_form = page.locator(".planning-test").nth(1)
    choose(
        agent_form.locator(".el-form-item").filter(has_text="绑定智能体"),
        "standalone-planning-test-agent",
    )
    agent_form.get_by_role("button", name="调用规划与推理服务").click()
    page.get_by_text("AGENT_BINDING", exact=True).wait_for(timeout=20_000)
    agent_ok = True
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    console_image = ASSET_DIR / "20260730-planning-dual-testbench.png"
    page.screenshot(path=str(console_image), full_page=True)

    page.goto(
        f"{BASE_URL}/agents/standalone-planning-test-agent/planning",
        wait_until="networkidle",
    )
    page.get_by_role("button", name="真实调用").click()
    page.locator(".planning-panel__result").filter(has_text="NEEDS_CLARIFICATION").wait_for(timeout=20_000)
    client_ok = True
    client_image = ASSET_DIR / "20260730-planning-test-agent.png"
    page.screenshot(path=str(client_image), full_page=True)

    print(json.dumps({
        "serviceDirect": direct_ok,
        "agentBinding": agent_ok,
        "clientAgent": client_ok,
        "consoleErrors": console_errors,
        "screenshots": [str(console_image), str(client_image)],
    }, ensure_ascii=False))
    browser.close()
