import json
import os
import time

from playwright.sync_api import sync_playwright


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
        data={"username": "admin", "password": os.environ["GENB_TEST_PASSWORD"]},
    )
    token = login.json()["data"]["token"]
    page.goto("http://localhost:9100/portal/login", wait_until="networkidle")
    page.evaluate(
        """token => {
          localStorage.setItem('token', token)
          localStorage.setItem('genb-client-token', token)
        }""",
        token,
    )

    page.goto(
        "http://localhost:9100/genb/core-components/SHORT_TERM_MEMORY",
        wait_until="networkidle",
    )
    if page.get_by_role("tab", name="智能体绑定").count() == 0:
        raise RuntimeError(
            f"binding tab missing: url={page.url}; body={page.locator('body').inner_text()[:2000]}"
        )
    page.get_by_role("tab", name="智能体绑定").click()
    page.get_by_text("短期记忆核心组件专用测试智能体", exact=True).wait_for(
        timeout=20_000
    )
    binding_ok = (
        page.get_by_text("standalone-memory-test-agent", exact=True).count() > 0
    )

    page.locator(".user-info").click()
    page.get_by_text("退出登录", exact=True).click()
    page.wait_for_url("**/portal/login", timeout=10_000)
    console_logout_ok = page.url.endswith("/portal/login")
    page.goto("http://localhost:9100/genb/dashboard", wait_until="networkidle")
    page.wait_for_url("**/portal/login", timeout=10_000)
    guard_ok = page.url.endswith("/portal/login")

    page.evaluate(
        """token => {
          localStorage.setItem('token', token)
          localStorage.setItem('genb-client-token', token)
        }""",
        token,
    )
    page.goto(
        "http://localhost:9100/agents/standalone-memory-test-agent/chat",
        wait_until="networkidle",
    )
    timestamp = int(time.time())
    task_id = f"browser-chat-task-{timestamp}"
    session_id = f"browser-chat-session-{timestamp}"
    inputs = page.locator(".scope-fields input")
    inputs.nth(0).fill(task_id)
    inputs.nth(1).fill(session_id)
    textarea = page.locator("textarea")
    textarea.fill("第一轮：记住编号B730")
    page.get_by_role("button", name="发送", exact=True).click()
    try:
        page.get_by_text("已写入短期记忆", exact=False).wait_for(timeout=20_000)
    except Exception as error:
        raise RuntimeError(
            f"first chat failed: url={page.url}; body={page.locator('body').inner_text()[:3000]}; console={console_errors}"
        ) from error
    textarea.fill("第二轮：请继续并读取之前的上下文")
    page.get_by_role("button", name="发送", exact=True).click()
    page.get_by_text("读取 2 条历史消息", exact=False).wait_for(timeout=20_000)
    chat_ok = page.get_by_text("读取 2 条历史消息", exact=False).count() > 0

    page.get_by_role("button", name="退出登录").click()
    page.wait_for_url("**/portal/login", timeout=10_000)
    client_logout_ok = page.url.endswith("/portal/login")
    print(
        json.dumps(
            {
                "bindingNameAndId": binding_ok,
                "consoleLogout": console_logout_ok,
                "consoleGuardAfterLogout": guard_ok,
                "twoTurnMemoryChat": chat_ok,
                "clientLogout": client_logout_ok,
                "consoleErrors": console_errors,
            },
            ensure_ascii=False,
        )
    )
    browser.close()
