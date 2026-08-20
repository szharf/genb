from __future__ import annotations

from pathlib import Path
import time

from playwright.sync_api import BrowserContext, sync_playwright


ENTRY = "http://127.0.0.1:18081/agents/core-component-demo-agent/"
LOGIN = ("http://127.0.0.1:18081/agents/_auth/login?agentId=core-component-demo-agent"
         "&returnPath=/agents/core-component-demo-agent/")
OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "m5-real-browser"
OUTPUT.mkdir(parents=True, exist_ok=True)
MARKER = f"M5真实栈偏好-{int(time.time())}"


def login(context: BrowserContext, username: str):
    page = context.new_page()
    page.goto(LOGIN)
    page.wait_for_load_state("networkidle")
    page.locator(f"#login-{username}").click()
    page.wait_for_url(ENTRY)
    page.wait_for_load_state("networkidle")
    return page


def send(page, message: str) -> None:
    page.locator("#messageInput").fill(message)
    page.locator(".send-button").click()
    page.wait_for_selector(".send-button:not([disabled])", timeout=30_000)


def long_search(page) -> list[dict]:
    return page.evaluate("""async () => {
      const response = await fetch('./api/component-tests/long-term/search', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sessionId: 'm5-isolation-check', query: '', sourceTypes: ['CONVERSATION']})
      });
      if (!response.ok) throw new Error('long search failed: ' + response.status);
      return (await response.json()).data.items;
    }""")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    admin_context = browser.new_context()
    admin = login(admin_context, "admin")
    errors: list[str] = []
    admin.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    admin.on("pageerror", lambda error: errors.append(str(error)))
    admin.locator("#newConversationButton").click()
    send(admin, "管理员本轮偏好Markdown检查表")
    send(admin, "我刚才告诉了你什么？")
    admin.wait_for_selector("#phaseBadge:text('验证完成')")
    admin.screenshot(path=str(OUTPUT / "real-short-term.png"), full_page=True)

    admin.locator("[data-scenario=long]").click()
    admin.locator("#newConversationButton").click()
    send(admin, MARKER)
    admin.locator("[data-action=new-long-session]").click()
    send(admin, "你还记得我的长期偏好吗？")
    admin.wait_for_selector("#phaseBadge:text('验证完成')", timeout=30_000)
    assert any(MARKER in item["content"] for item in long_search(admin))
    admin.screenshot(path=str(OUTPUT / "real-long-term.png"), full_page=True)

    admin.locator("[data-scenario=skill]").click()
    admin.locator("#newConversationButton").click()
    send(admin, "帮我生成材料检查Skill")
    admin.locator("[data-action=skill-complete-example]").click()
    admin.locator(".send-button").click()
    admin.wait_for_selector("#phaseBadge:text('验证完成')", timeout=30_000)
    admin.screenshot(path=str(OUTPUT / "real-skill.png"), full_page=True)
    admin.reload(); admin.wait_for_load_state("networkidle")
    admin.locator("[data-scenario=skill]").click()
    assert "材料检查" in admin.locator("body").inner_text()

    user_context = browser.new_context()
    user = login(user_context, "test_user")
    user_items = long_search(user)
    assert all(MARKER not in item["content"] for item in user_items)
    user.locator("#newConversationButton").click()
    send(user, "测试用户自己的短期标记")
    send(user, "我刚才告诉了你什么？")
    user.wait_for_selector("#phaseBadge:text('验证完成')")
    user.screenshot(path=str(OUTPUT / "real-second-user-isolation.png"), full_page=True)

    if errors:
        raise AssertionError("browser errors before logout: " + " | ".join(errors))

    for page in (admin, user):
        statuses = page.evaluate("""async () => {
          const logout = await fetch('/agents/_auth/logout', {
            method: 'POST', headers: {'Origin': 'http://127.0.0.1:18081'}
          });
          const protectedResponse = await fetch(
            '/agents/core-component-demo-agent/api/session', {redirect: 'manual'}
          );
          return [logout.status, protectedResponse.status];
        }""")
        assert statuses == [204, 401], statuses
    browser.close()
print(f"M5_REAL_FULL_STACK_BROWSER_OK marker={MARKER}")
