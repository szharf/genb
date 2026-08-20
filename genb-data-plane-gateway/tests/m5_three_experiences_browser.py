from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "m5-browser"
OUTPUT.mkdir(parents=True, exist_ok=True)
WEB = Path(__file__).resolve().parents[2] / "control-system-test-agent" / "src" / "control_system_test_agent" / "web_ui"


def response(route, data=None, status=200):
    body = "" if status == 204 else json.dumps({"data": data}, ensure_ascii=False)
    route.fulfill(status=status, content_type="application/json", body=body)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    page = browser.new_page()
    errors = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/assets/app.js*", lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=(WEB / "app.js").read_text(encoding="utf-8"),
    ))
    page.route("**/assets/styles.css*", lambda route: route.fulfill(
        status=200, content_type="text/css", body=(WEB / "styles.css").read_text(encoding="utf-8"),
    ))

    def api(route):
        request = route.request
        path = request.url.split("/api/", 1)[1]
        if path == "session": return response(route, {"agentId":"core-component-demo-agent", "userId":1, "username":"alice"})
        if path.startswith("conversations?"): return response(route, [])
        if path.startswith("conversations/"): return response(route, status=204)
        if path == "component-tests/short-term":
            return response(route, {"contextMessageCount":1, "committed":True, "warnings":[]})
        if path == "component-tests/long-term/extractions":
            return response(route, {"status":"SUCCEEDED", "writtenCount":1, "rejectedCount":0})
        if path == "component-tests/long-term/search":
            return response(route, {"items":[{"content":"偏好Markdown检查表", "memoryId":"m1", "type":"USER_PREFERENCE",
                                                       "confidence":0.98, "sourceType":"CONVERSATION", "sourceRef":"c1"}]})
        if path == "customer/chat":
            payload = request.post_data_json
            if "PDF" in payload["message"]:
                return response(route, {"answer":"Skill已经生成。", "mode":"SKILL_READY", "skill":{"name":"材料检查"},
                                        "planning":{}, "diagnostics":{}, "committed":True})
            return response(route, {"answer":"请补充输入格式。", "mode":"CLARIFY", "skill":None,
                                    "planning":{"questions":["输入材料是什么格式？"]}, "diagnostics":{}, "committed":False})
        route.abort()

    page.route("**/api/**", api)
    page.goto("http://127.0.0.1:18715/index.html")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)

    def send(message):
        page.locator("#messageInput").fill(message)
        page.locator(".send-button").click()

    send("我偏好Markdown检查表")
    send("我刚才告诉了你什么？")
    page.wait_for_selector("#phaseBadge:text('验证完成')")
    page.screenshot(path=str(OUTPUT / "short-term-complete.png"), full_page=True)

    page.locator("[data-scenario=long]").click()
    send("我长期偏好Markdown检查表")
    page.locator("[data-action=new-long-session]").click()
    send("你还记得我的长期偏好吗？")
    page.wait_for_selector("#phaseBadge:text('验证完成')")
    page.screenshot(path=str(OUTPUT / "long-term-complete.png"), full_page=True)

    page.locator("[data-scenario=skill]").click()
    send("帮我生成材料检查Skill")
    page.locator("[data-action=skill-complete-example]").click()
    page.locator(".send-button").click()
    page.wait_for_selector("#phaseBadge:text('验证完成')")
    page.screenshot(path=str(OUTPUT / "skill-complete.png"), full_page=True)
    browser.close()

if errors:
    raise AssertionError("browser errors: " + " | ".join(errors))
print("M5_THREE_EXPERIENCES_BROWSER_OK")
