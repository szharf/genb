from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright


OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "m5-browser"
OUTPUT.mkdir(parents=True, exist_ok=True)
ENTRY = "http://127.0.0.1:18081/agents/core-component-demo-agent/"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    context = browser.new_context()
    page = context.new_page(); errors = []; capture = {"enabled":True}
    page.on("console", lambda message: errors.append(message.text)
            if capture["enabled"] and message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)) if capture["enabled"] else None)
    context.route("**/favicon.ico", lambda route: route.fulfill(status=204, body=""))

    login = context.request.get(
        "http://127.0.0.1:18081/agents/_auth/login?agentId=core-component-demo-agent"
        "&returnPath=/agents/core-component-demo-agent/", max_redirects=0,
    )
    assert login.status == 303
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    page.set_content(
        "<!doctype html><meta charset=utf-8><a id=authorize "
        f"href='http://127.0.0.1:18081/agents/_auth/callback?code={'c' * 40}&state={state}'>Authorize</a>"
    )
    page.locator("#authorize").click(); page.wait_for_url(ENTRY)
    page.wait_for_load_state("networkidle")
    page.locator("#newConversationButton").click()
    page.wait_for_timeout(100)

    def send(message):
        page.locator("#messageInput").fill(message)
        page.locator(".send-button").click()
        page.wait_for_selector(".send-button:not([disabled])")

    send("我偏好Markdown检查表")
    send("我刚才告诉了你什么？")
    page.wait_for_selector("#phaseBadge:text('验证完成')")
    page.screenshot(path=str(OUTPUT / "full-short-term.png"), full_page=True)

    page.locator("[data-scenario=long]").click()
    page.locator("#newConversationButton").click()
    page.wait_for_timeout(100)
    send("我长期偏好Markdown检查表")
    page.locator("[data-action=new-long-session]").click()
    send("你还记得我的长期偏好吗？")
    page.wait_for_selector("#phaseBadge:text('验证完成')")
    page.screenshot(path=str(OUTPUT / "full-long-term.png"), full_page=True)

    page.locator("[data-scenario=skill]").click()
    page.locator("#newConversationButton").click()
    page.wait_for_timeout(100)
    send("帮我生成材料检查Skill")
    page.locator("[data-action=skill-complete-example]").click()
    page.locator(".send-button").click()
    page.wait_for_selector("#phaseBadge:text('验证完成')")
    page.screenshot(path=str(OUTPUT / "full-skill.png"), full_page=True)

    page.reload(); page.wait_for_load_state("networkidle")
    page.locator("[data-scenario=skill]").click()
    assert "材料检查" in page.locator("body").inner_text()
    page.locator("#logoutButton").click()
    capture["enabled"] = False
    response = page.goto(ENTRY)
    assert response.status == 401
    browser.close()

if errors:
    raise AssertionError("browser errors: " + " | ".join(errors))
print("M5_FULL_STACK_BROWSER_OK")
