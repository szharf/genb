from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright


OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "m5-browser"
OUTPUT.mkdir(parents=True, exist_ok=True)
errors = []
capture_errors = {"enabled": True}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    context = browser.new_context()
    page = context.new_page()
    page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}")
            if capture_errors["enabled"] and message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(f"pageerror:{error}"))
    context.route("**/favicon.ico", lambda route: route.fulfill(status=204, body=""))

    login = context.request.get(
        "http://127.0.0.1:18081/agents/_auth/login?agentId=agent-a&returnPath=/agents/agent-a/chat",
        max_redirects=0,
    )
    assert login.status == 303
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    page.set_content(
        "<!doctype html><meta charset=utf-8><title>Local Portal</title>"
        f"<a id=authorize href='http://127.0.0.1:18081/agents/_auth/callback?code={'a' * 40}&state={state}'>Authorize</a>"
    )
    page.locator("#authorize").click()
    page.wait_for_url("**/agents/agent-a/chat")
    assert page.locator("body").inner_text() == '{"agent":"stateless","ok":true}'
    page.screenshot(path=str(OUTPUT / "agent-a-after-login.png"), full_page=True)

    page.reload(); page.wait_for_load_state("networkidle")
    assert page.locator("body").inner_text() == '{"agent":"stateless","ok":true}'
    inspected = page.evaluate("""async () => (await fetch('/agents/agent-a/inspect', {
      headers: {'X-GenB-Forged':'attacker', 'X-GenB-User-Id':'admin'}
    })).json()""")
    assert inspected == {"forgedHeaderReceived": False, "gatewayCookieReceived": False, "trustedUserId": "user-a"}

    stream = page.evaluate("""async () => await new Promise((resolve, reject) => {
      const events=[]; const source=new EventSource('/agents/agent-a/events');
      source.addEventListener('message', event => events.push(event.data));
      source.addEventListener('complete', event => { events.push(event.data); source.close(); resolve(events); });
      source.onerror=reject;
    })""")
    assert stream == ["first", "done"]

    status = page.evaluate("""async () => (await fetch('/agents/_auth/logout', {method:'POST'})).status""")
    assert status == 204
    capture_errors["enabled"] = False
    response = page.goto("http://127.0.0.1:18081/agents/agent-a/chat")
    assert response.status == 401
    page.screenshot(path=str(OUTPUT / "agent-a-after-logout.png"), full_page=True)
    browser.close()

if errors:
    raise AssertionError("browser errors: " + " | ".join(errors))
print("M5_BROWSER_ACCEPTANCE_OK")
