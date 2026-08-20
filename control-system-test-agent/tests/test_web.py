from dataclasses import dataclass

from fastapi.testclient import TestClient

from control_system_test_agent import web as web_module
from control_system_test_agent.errors import RemoteCallError
from control_system_test_agent.models import (
    ChatResult,
    CustomerChatResult,
    CustomerDiagnostics,
    ExtractionStatus,
    LongTermMemoryItem,
)
from control_system_test_agent.web import (
    CustomerSession,
    create_app,
    get_agent,
    get_customer_agent,
    get_customer_session,
    get_planning_agent,
    get_session_store,
    get_sso_client,
)


@dataclass
class FakeAgent:
    calls: list[dict[str, str]]

    async def chat(self, **kwargs: str) -> ChatResult:
        self.calls.append(kwargs)
        return ChatResult(
            answer="测试回答（已读取2条上下文）：继续",
            context_message_count=2,
            committed=True,
            warnings=(),
        )


def test_chat_api_uses_request_user_token_without_exposing_service_credential(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "standalone-memory-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakeAgent([])
    application = create_app()
    application.dependency_overrides[get_agent] = lambda: fake

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            headers={"Authorization": "Bearer user-token-a"},
            json={"taskId": "task-a", "sessionId": "session-a", "message": "继续"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["contextMessageCount"] == 2
    assert fake.calls[0]["user_token"] == "user-token-a"
    assert "server-only-secret" not in response.text


def test_chat_api_rejects_missing_user_token(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "standalone-memory-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    application = create_app()
    application.dependency_overrides[get_agent] = lambda: FakeAgent([])

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json={"taskId": "task-a", "sessionId": "session-a", "message": "继续"},
        )

    assert response.status_code == 401


@dataclass
class FakePlanningAgent:
    calls: list[dict[str, object]]

    async def invoke(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"status": "READY", "questions": []}


def test_planning_api_uses_user_token_and_returns_service_result(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "standalone-planning-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakePlanningAgent([])
    application = create_app()
    application.dependency_overrides[get_planning_agent] = lambda: fake

    with TestClient(application) as client:
        response = client.post(
            "/api/planning",
            headers={"Authorization": "Bearer user-token-a"},
            json={
                "sessionId": "session-plan", "operation": "ANALYZE",
                "payload": {"goal": "生成授信检查Skill"},
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "READY"
    assert fake.calls[0]["user_token"] == "user-token-a"
    assert "server-only-secret" not in response.text


def test_planning_api_maps_invalid_operation_payload_to_bad_request(monkeypatch) -> None:
    class InvalidPlanningAgent:
        async def invoke(self, **_kwargs: object) -> dict[str, object]:
            raise ValueError("REVISE requires skillId")

    monkeypatch.setenv("AGENT_ID", "standalone-planning-test-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    application = create_app()
    application.dependency_overrides[get_planning_agent] = lambda: InvalidPlanningAgent()
    with TestClient(application) as client:
        response = client.post(
            "/api/planning", headers={"Authorization": "Bearer user-token-a"},
            json={"sessionId": "session-plan", "operation": "REVISE", "payload": {}},
        )
    assert response.status_code == 400


@dataclass
class FakeCustomerAgent:
    calls: list[dict[str, str]]

    async def chat(self, **kwargs: str) -> CustomerChatResult:
        self.calls.append(kwargs)
        return CustomerChatResult(
            answer="你正在办理A公司授信。",
            mode="CHAT",
            skill=None,
            committed=True,
            diagnostics=CustomerDiagnostics(
                component_session_id="cs-customer",
                components=("SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE"),
                context_message_count=2,
                provider="deepseek-direct",
                model="deepseek-chat",
                input_tokens=20,
                output_tokens=10,
                request_id="req-model",
            ),
        )


def test_customer_chat_is_a_natural_language_interface_and_keeps_secrets_server_side(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakeCustomerAgent([])
    application = create_app()
    application.dependency_overrides[get_customer_agent] = lambda: fake
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
    )

    class ValidSessionStore:
        async def get(self, _session_id: str) -> CustomerSession:
            return CustomerSession(
                "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application.dependency_overrides[get_session_store] = lambda: ValidSessionStore()

    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        page = client.get("/")
        response = client.post(
            "/api/customer/chat",
            headers={"Authorization": "Bearer user-token-a"},
            json={"taskId": "task-a", "sessionId": "session-a", "message": "我在办理什么业务？"},
        )

    assert page.status_code == 200
    assert "能力体验" in page.text
    assert 'id="conversationThread"' in page.text
    assert 'id="messageComposer"' in page.text
    assert "一步步生成Skill" in page.text
    assert 'id="liveStatus"' in page.text
    assert response.status_code == 200
    assert response.json()["data"]["answer"] == "你正在办理A公司授信。"
    assert response.json()["data"]["diagnostics"]["components"] == [
        "SHORT_TERM_MEMORY", "PLANNING_REASONING", "INFERENCE_ENGINE"
    ]
    assert fake.calls[0]["message"] == "我在办理什么业务？"
    assert fake.calls[0]["session_grant"] == "agent-session-grant"
    assert "user_token" not in fake.calls[0]
    assert "server-only-secret" not in response.text


def test_customer_page_assets_call_each_component_through_its_own_interface() -> None:
    application = create_app()
    with TestClient(application) as client:
        script = client.get("/assets/app.js")

    assert script.status_code == 200
    assert "handleShort" in script.text
    assert "handleLong" in script.text
    assert "handleSkill" in script.text
    assert "./api/component-tests/short-term" in script.text
    assert "./api/component-tests/long-term/extractions" in script.text
    assert "./api/component-tests/long-term/search" in script.text
    assert "./api/customer/chat" in script.text
    assert "crypto.randomUUID()" in script.text
    assert "current.evidence = data" in script.text
    assert "query: ''" in script.text
    assert "const completed = current.phase >= 2" in script.text
    assert "为了把这个Skill做对" in script.text
    assert "skill-complete-example" in script.text
    assert "input.value = ''\n  input.style.height = 'auto'" in script.text


def test_customer_page_creates_switches_and_restores_real_conversations() -> None:
    application = create_app()
    with TestClient(application) as client:
        script = client.get("/assets/app.js")

    assert script.status_code == 200
    assert "function createConversationState" in script.text
    assert "function renderConversationList" in script.text
    assert "async function loadConversationHistory" in script.text
    assert "async function saveConversation" in script.text
    assert "./api/conversations?scenario=" in script.text
    assert "./api/conversations/${current.conversationId}" in script.text
    assert "newConversationButton" in script.text
    assert "conversationId" in script.text
    assert "新的会话已经开始" not in script.text


def test_async_reply_stays_with_the_scenario_that_sent_the_request() -> None:
    application = create_app()
    with TestClient(application) as client:
        script = client.get("/assets/app.js")

    assert script.status_code == 200
    assert "const scenarioKey = state.active" in script.text
    assert "const current = activeState()" in script.text
    assert "const current = state.scenarios[scenarioKey]" not in script.text
    assert "if (scenarioKey === 'short') await handleShort(current, message.trim())" in script.text
    assert "else if (scenarioKey === 'long') await handleLong(current, message.trim())" in script.text
    assert "else await handleSkill(current, message.trim())" in script.text
    assert "function addMessage(current, role, text, error = false)" in script.text
    assert "activeState()?.conversationId === current.conversationId" in script.text
    assert "busy: false" in script.text
    assert "authenticated: false,\n  busy: false" not in script.text


def test_customer_page_is_a_plain_language_conversation_not_an_engineering_form() -> None:
    class ValidSessionStore:
        async def get(self, _session_id: str) -> CustomerSession:
            return CustomerSession(
                "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: ValidSessionStore()
    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        page = client.get("/")

    assert page.status_code == 200
    assert 'id="conversationThread"' in page.text
    assert 'id="messageComposer"' in page.text
    assert "记住本次交流" in page.text
    assert "跨会话记住我" in page.text
    assert "一步步生成Skill" in page.text
    assert "Task ID" not in page.text
    assert "Session ID" not in page.text
    assert "JSON参数" not in page.text
    assert "ANALYZE ·" not in page.text


def test_customer_page_uses_an_inline_favicon_without_a_failing_network_request() -> None:
    class ValidSessionStore:
        async def get(self, _session_id: str) -> CustomerSession:
            return CustomerSession(
                "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: ValidSessionStore()
    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        page = client.get("/")

    assert page.status_code == 200
    assert 'rel="icon"' in page.text
    assert 'href="data:image/svg+xml,' in page.text


def test_customer_page_separates_three_core_component_test_workspaces() -> None:
    class ValidSessionStore:
        async def get(self, _session_id: str) -> CustomerSession:
            return CustomerSession(
                "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: ValidSessionStore()
    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        page = client.get("/")

    assert page.status_code == 200
    for scenario in ("short", "long", "skill"):
        assert f'data-scenario="{scenario}"' in page.text
    assert 'id="conversationThread"' in page.text
    assert 'id="technicalEvidence"' in page.text
    assert "Task ID" not in page.text
    assert "Session ID" not in page.text


def test_customer_page_shows_retained_conversations_and_a_real_new_chat_action() -> None:
    class ValidSessionStore:
        async def get(self, _session_id: str) -> CustomerSession:
            return CustomerSession(
                "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: ValidSessionStore()
    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        page = client.get("/")

    assert page.status_code == 200
    assert 'id="conversationHistory"' in page.text
    assert 'id="conversationList"' in page.text
    assert 'id="newConversationButton"' in page.text
    assert "本场景的对话" in page.text
    assert "新建对话" in page.text


def test_authenticated_user_can_save_and_list_their_conversations() -> None:
    saved: list[tuple[int, dict[str, object]]] = []

    class FakeConversationStore:
        async def save(self, user_id: int, conversation: dict[str, object]) -> None:
            saved.append((user_id, conversation))

        async def list(self, user_id: int, scenario: str) -> list[dict[str, object]]:
            return [item for owner, item in saved if owner == user_id and item["scenario"] == scenario]

    application = create_app()
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
    )
    conversation_dependency = getattr(web_module, "get_conversation_store", None)
    if conversation_dependency is not None:
        application.dependency_overrides[conversation_dependency] = lambda: FakeConversationStore()
    payload = {
        "scenario": "long",
        "title": "我的稳健偏好",
        "taskId": "long-task-a",
        "sessionId": "long-session-a",
        "phase": 1,
        "firstMessage": "我长期偏好稳健方案",
        "messages": [
            {"role": "user", "text": "我长期偏好稳健方案", "error": False},
            {"role": "assistant", "text": "好的，我记住了。", "error": False},
        ],
        "suggestions": [],
        "evidence": None,
        "skill": None,
    }

    with TestClient(application) as client:
        saved_response = client.put("/api/conversations/long-conversation-a", json=payload)
        listed_response = client.get("/api/conversations", params={"scenario": "long"})

    assert saved_response.status_code == 204
    assert listed_response.status_code == 200
    assert listed_response.json()["data"][0]["conversationId"] == "long-conversation-a"
    assert listed_response.json()["data"][0]["messages"][0]["text"] == "我长期偏好稳健方案"
    assert saved[0][0] == 42


def test_short_term_component_test_uses_only_server_session_identity(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakeAgent([])
    application = create_app()
    application.dependency_overrides[get_agent] = lambda: fake
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/component-tests/short-term",
            json={"taskId": "task-short-a", "sessionId": "session-short-a", "message": "第一轮"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["componentCode"] == "SHORT_TERM_MEMORY"
    assert response.json()["data"]["contextMessageCount"] == 2
    assert fake.calls == [{
        "session_grant": "server-only-session-grant",
        "task_id": "task-short-a",
        "session_id": "session-short-a",
        "message": "第一轮",
    }]
    assert "session-grant" not in response.text
    assert "server-only-secret" not in response.text


def test_long_term_component_test_separates_extraction_and_cross_session_search(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")

    class FakeLongTermAgent:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def store_long_term(self, **kwargs: object) -> ExtractionStatus:
            self.calls.append(("extract", kwargs))
            return ExtractionStatus("ext-a", "SUCCEEDED", 1, 0)

        async def recall_long_term(self, **kwargs: object) -> tuple[LongTermMemoryItem, ...]:
            self.calls.append(("search", kwargs))
            return (LongTermMemoryItem(
                memory_id="mem-a", memory_type="USER_PREFERENCE",
                content="偏好稳健方案", confidence=0.96,
                source_type="CONVERSATION", source_ref="turn-a",
            ),)

    fake = FakeLongTermAgent()
    application = create_app()
    application.dependency_overrides[get_agent] = lambda: fake
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
    )

    with TestClient(application) as client:
        extracted = client.post(
            "/api/component-tests/long-term/extractions",
            json={"sessionId": "session-write-a", "message": "我长期偏好稳健方案"},
        )
        searched = client.post(
            "/api/component-tests/long-term/search",
            json={
                "sessionId": "session-search-b", "query": "稳健",
                "sourceTypes": ["CONVERSATION"],
            },
        )

    assert extracted.status_code == 200
    assert extracted.json()["data"] == {
        "componentCode": "LONG_TERM_MEMORY", "extractionId": "ext-a",
        "status": "SUCCEEDED", "writtenCount": 1, "rejectedCount": 0,
    }
    assert searched.status_code == 200
    assert searched.json()["data"]["items"][0]["sourceType"] == "CONVERSATION"
    assert searched.json()["data"]["items"][0]["sourceRef"] == "turn-a"
    assert fake.calls[0][1]["session_grant"] == "server-only-session-grant"
    assert fake.calls[1][1]["session_id"] == "session-search-b"
    assert fake.calls[1][1]["source_types"] == ("CONVERSATION",)
    assert "session-grant" not in searched.text


def test_planning_component_test_uses_only_planning_agent_and_server_session(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakePlanningAgent([])
    application = create_app()
    application.dependency_overrides[get_planning_agent] = lambda: fake
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/component-tests/planning",
            json={
                "sessionId": "session-plan-a", "operation": "ANALYZE",
                "payload": {"goal": "生成授信检查Skill"},
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["componentCode"] == "PLANNING_REASONING"
    assert response.json()["data"]["result"]["status"] == "READY"
    assert fake.calls == [{
        "session_grant": "server-only-session-grant",
        "session_id": "session-plan-a",
        "operation": "ANALYZE",
        "payload": {"goal": "生成授信检查Skill"},
    }]
    assert "session-grant" not in response.text


def test_customer_page_redirects_to_login_when_agent_session_is_missing() -> None:
    class MissingSessionStore:
        async def get(self, _session_id: str) -> None:
            return None

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: MissingSessionStore()

    with TestClient(application) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_gateway_identity_opens_workspace_without_second_agent_login(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "machine-credential")
    application = create_app()
    headers = {
        "X-GenB-Identity-Token":"signed-gateway-identity",
        "X-GenB-User-Id":"42",
        "X-GenB-Agent-Id":"core-component-demo-agent",
    }
    with TestClient(application) as client:
        page = client.get("/", headers=headers, follow_redirects=False)
        session = client.get("/api/session", headers=headers)

    assert page.status_code == 200
    assert session.json()["data"] == {
        "agentId":"core-component-demo-agent", "userId":42, "username":"42",
    }


def test_customer_page_uses_only_the_agent_server_session() -> None:
    application = create_app()
    with TestClient(application) as client:
        script = client.get("/assets/app.js")

    assert "./api/session" in script.text
    assert "./auth/login" in script.text
    assert "credentials: 'include'" in script.text
    assert "genesis-portal-token" not in script.text
    assert "genb-client-token" not in script.text
    assert "/api/v1/genesis/sso/gen-b/token" not in script.text


def test_conversation_layout_has_a_mobile_chat_first_mode() -> None:
    application = create_app()
    with TestClient(application) as client:
        stylesheet = client.get("/assets/styles.css")

    assert stylesheet.status_code == 200
    assert "@media (max-width: 820px)" in stylesheet.text
    assert ".chat-card { height: calc(100dvh - 192px);" in stylesheet.text
    assert ".guide-card:not(.goal-card), .evidence-card { display: none; }" in stylesheet.text


def test_customer_workspace_keeps_document_scroll_locked_to_the_viewport() -> None:
    application = create_app()
    with TestClient(application) as client:
        stylesheet = client.get("/assets/styles.css")

    assert stylesheet.status_code == 200
    assert "html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; }" in stylesheet.text
    assert ".app-shell { display: grid; grid-template-columns: 290px minmax(0, 1fr); height: 100dvh; }" in stylesheet.text
    assert ".conversation-layout { min-height: 0;" in stylesheet.text
    assert ".conversation-thread { min-height: 0; overflow: auto;" in stylesheet.text


def test_conversation_area_owns_the_flexible_viewport_row() -> None:
    application = create_app()
    with TestClient(application) as client:
        stylesheet = client.get("/assets/styles.css")

    assert stylesheet.status_code == 200
    assert ".experience-main { min-width: 0; height: 100dvh; display: grid; grid-template-rows: auto minmax(0,1fr);" in stylesheet.text
    assert ".conversation-thread { min-height: 0; overflow: auto;" in stylesheet.text


def test_conversation_scrolls_to_the_latest_answer_after_execution() -> None:
    application = create_app()
    with TestClient(application) as client:
        script = client.get("/assets/app.js")

    assert script.status_code == 200
    assert "requestAnimationFrame" in script.text
    assert "thread.scrollTop = thread.scrollHeight" in script.text


def test_customer_chat_distinguishes_model_outage_from_missing_binding(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")

    class FailingCustomerAgent:
        async def chat(self, **_kwargs: str):
            raise RemoteCallError(operation="planning converse", status_code=502, request_id="req-x")

    application = create_app()
    application.dependency_overrides[get_customer_agent] = lambda: FailingCustomerAgent()
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
    )
    with TestClient(application) as client:
        response = client.post(
            "/api/customer/chat",
            headers={"Authorization": "Bearer user-token-a"},
            json={"taskId": "task-a", "sessionId": "session-a", "message": "生成Skill"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "规划或模型服务暂时不可用，请稍后重试"


def test_customer_chat_rejects_browser_bearer_without_agent_server_session(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    fake = FakeCustomerAgent([])
    application = create_app()
    application.dependency_overrides[get_customer_agent] = lambda: fake

    with TestClient(application) as client:
        response = client.post(
            "/api/customer/chat",
            headers={"Authorization": "Bearer browser-token-must-not-be-accepted"},
            json={"taskId": "task-a", "sessionId": "session-a", "message": "继续"},
        )

    assert response.status_code == 401
    assert fake.calls == []


def test_session_api_returns_minimum_identity_without_server_grant() -> None:
    application = create_app()
    application.dependency_overrides[get_customer_session] = lambda: CustomerSession(
        "agent-session-grant-must-stay-server-side",
        "core-component-demo-agent",
        42,
        "customer-a",
    )

    with TestClient(application) as client:
        response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "agentId": "core-component-demo-agent",
        "userId": 42,
        "username": "customer-a",
    }
    assert "session-grant" not in response.text


def test_auth_callback_creates_only_an_httponly_lax_agent_cookie(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    monkeypatch.setenv("AGENT_CALLBACK_URL", "http://localhost:18714/auth/callback")

    class FakeStore:
        async def create(self, session: CustomerSession) -> str:
            assert session.session_grant == "server-only-session-grant"
            return "opaque-browser-session-id"

    class FakeSso:
        async def exchange(self, **_kwargs) -> CustomerSession:
            return CustomerSession(
                "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: FakeStore()
    application.dependency_overrides[get_sso_client] = lambda: FakeSso()

    with TestClient(application) as client:
        client.cookies.set("genb_agent_login_state", "state-0123456789-abcdefghijklmnop")
        response = client.get(
            "/auth/callback",
            params={
                "code": "authorization-code-with-at-least-32-bytes",
                "state": "state-0123456789-abcdefghijklmnop",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    cookie = response.headers["set-cookie"]
    assert "genb_agent_session=opaque-browser-session-id" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "server-only-session-grant" not in cookie


def test_auth_login_redirects_to_portal_with_state_and_registered_callback(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    monkeypatch.setenv("AGENT_CALLBACK_URL", "http://localhost:18714/auth/callback")
    monkeypatch.setenv("PORTAL_AGENT_SSO_URL", "http://localhost:9100/agent-sso")

    with TestClient(create_app()) as client:
        response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("http://localhost:9100/agent-sso?")
    assert "agentId=core-component-demo-agent" in response.headers["location"]
    assert "callbackUrl=http%3A%2F%2Flocalhost%3A18714%2Fauth%2Fcallback" in response.headers["location"]
    assert "state=" in response.headers["location"]
    assert "server-only-secret" not in response.headers["location"]
    assert "genb_agent_login_state=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_auth_logout_revokes_server_grant_and_deletes_browser_session(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    monkeypatch.setenv("PORTAL_AGENT_LOGOUT_URL", "http://localhost:9100/agent-sso/logout")
    calls: list[tuple[str, str]] = []

    class FakeStore:
        async def get(self, session_id: str) -> CustomerSession | None:
            calls.append(("get", session_id))
            return CustomerSession(
                "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

        async def delete(self, session_id: str) -> None:
            calls.append(("delete", session_id))

    class FakeSso:
        async def logout(self, *, session_grant: str) -> None:
            calls.append(("revoke", session_grant))

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: FakeStore()
    application.dependency_overrides[get_sso_client] = lambda: FakeSso()

    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        response = client.post("/auth/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:9100/agent-sso/logout"
    assert calls == [
        ("get", "opaque-browser-session-id"),
        ("revoke", "server-only-session-grant"),
        ("delete", "opaque-browser-session-id"),
    ]
    assert "genb_agent_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "server-only-session-grant" not in response.headers["set-cookie"]


def test_customer_page_exposes_unified_logout_action() -> None:
    class ValidSessionStore:
        async def get(self, _session_id: str) -> CustomerSession:
            return CustomerSession(
                "agent-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: ValidSessionStore()
    with TestClient(application) as client:
        client.cookies.set("genb_agent_session", "opaque-browser-session-id")
        response = client.get("/")
        script = client.get("/assets/app.js")

    assert 'id="logoutButton"' in response.text
    assert 'action="/agents/_auth/logout"' in response.text


def test_agent_login_refresh_chat_and_logout_use_one_server_side_session(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ID", "core-component-demo-agent")
    monkeypatch.setenv("GENB_BASE_URL", "http://genb.local/api")
    monkeypatch.setenv("SERVICE_CREDENTIAL", "server-only-secret")
    sessions: dict[str, CustomerSession] = {}
    revoked: list[str] = []

    class FakeStore:
        async def create(self, session: CustomerSession) -> str:
            sessions["opaque-session-id"] = session
            return "opaque-session-id"

        async def get(self, session_id: str) -> CustomerSession | None:
            return sessions.get(session_id)

        async def delete(self, session_id: str) -> None:
            sessions.pop(session_id, None)

    class FakeSso:
        async def exchange(self, **_kwargs) -> CustomerSession:
            return CustomerSession(
                "server-only-session-grant", "core-component-demo-agent", 42, "customer-a"
            )

        async def logout(self, *, session_grant: str) -> None:
            revoked.append(session_grant)

    customer = FakeCustomerAgent([])
    application = create_app()
    application.dependency_overrides[get_session_store] = lambda: FakeStore()
    application.dependency_overrides[get_sso_client] = lambda: FakeSso()
    application.dependency_overrides[get_customer_agent] = lambda: customer

    with TestClient(application) as client:
        client.cookies.set("genb_agent_login_state", "state-0123456789-abcdefghijklmnop")
        callback = client.get(
            "/auth/callback",
            params={
                "code": "authorization-code-with-at-least-32-bytes",
                "state": "state-0123456789-abcdefghijklmnop",
            },
            follow_redirects=False,
        )
        refreshed = client.get("/api/session")
        chatted = client.post(
            "/api/customer/chat",
            json={"taskId": "task-a", "sessionId": "session-a", "message": "继续"},
        )
        logged_out = client.post("/auth/logout", follow_redirects=False)
        after_logout = client.get("/api/session")

    assert callback.status_code == 303
    assert refreshed.json()["data"]["username"] == "customer-a"
    assert chatted.status_code == 200
    assert customer.calls[0]["session_grant"] == "server-only-session-grant"
    assert logged_out.status_code == 303
    assert revoked == ["server-only-session-grant"]
    assert after_logout.status_code == 401
