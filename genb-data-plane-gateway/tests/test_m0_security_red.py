from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("GENB_GATEWAY_BASE_URL", "http://127.0.0.1:18080").rstrip("/")


class M0SecurityRedTest(unittest.TestCase):
    """Executable acceptance specifications that must be red before gateway implementation."""

    def test_old_agent_launches_through_the_unified_identity_aware_entry(self) -> None:
        source = (ROOT / "gen-b" / "gen-b-client" / "src" / "utils" / "agentLaunch.ts").read_text(encoding="utf-8")
        self.assertNotIn("http://47.116.69.17:${agent.port}", source)
        self.assertIn("/agents/${encodeURIComponent(agent.id)}/", source)

    def test_browser_forged_identity_headers_are_not_trusted(self) -> None:
        status, body, _ = self.request(
            "GET",
            "/internal/agent-access/authorize?agentId=fake-agent&requestPath=%2F",
            headers={"X-GenB-User-Id": "admin", "X-GenB-Tenant-Id": "forged"},
        )
        self.assertIn(status, {401, 403})
        self.assertNotIn("admin", body)

    def test_user_supplied_unknown_upstream_is_rejected(self) -> None:
        status, body, _ = self.request(
            "GET",
            "/internal/agent-access/authorize?agentId=fake-agent&requestPath=%2F",
            headers={"X-Upstream-URL": "http://169.254.169.254/latest/meta-data"},
        )
        self.assertIn(status, {400, 403, 404})
        self.assertNotIn("169.254.169.254", body)

    def test_unbound_capability_returns_stable_problem_details(self) -> None:
        status, body, content_type = self.invoke("SHORT_TERM_MEMORY", "appendMessage", token="valid-test-token")
        self.assert_problem(status, body, content_type, 403, "CAPABILITY_NOT_BOUND")

    def test_disabled_implementation_returns_stable_problem_details(self) -> None:
        status, body, content_type = self.invoke("PLANNING_REASONING", "analyzeRequirement", token="disabled-binding-token")
        self.assert_problem(status, body, content_type, 503, "IMPLEMENTATION_UNAVAILABLE")

    def test_expired_or_revoked_identity_never_uses_stale_authorization(self) -> None:
        for token in ("expired-test-token", "revoked-test-token"):
            status, body, content_type = self.invoke("LONG_TERM_MEMORY", "searchMemories", token=token)
            self.assert_problem(status, body, content_type, 401, "INVALID_IDENTITY_TOKEN")

    def test_errors_never_leak_secrets_tokens_or_real_upstream_addresses(self) -> None:
        _, body, headers = self.invoke("PLANNING_REASONING", "forceUpstreamFailure", token="valid-test-token")
        serialized_headers = json.dumps(dict(headers), ensure_ascii=False)
        for marker in ("service-secret", "actor-token", "session-grant", "api-key", "http://internal-"):
            self.assertNotIn(marker, body.lower())
            self.assertNotIn(marker, serialized_headers.lower())

    def test_stateful_capability_is_isolated_between_two_users(self) -> None:
        first_status, first_body, _ = self.invoke(
            "SHORT_TERM_MEMORY", "appendMessage", token="user-a-token", payload={"message": "only-user-a"}
        )
        self.assertEqual(200, first_status, first_body)
        second_status, second_body, _ = self.invoke(
            "SHORT_TERM_MEMORY", "listMessages", token="user-b-token", payload={}
        )
        self.assertEqual(200, second_status, second_body)
        self.assertNotIn("only-user-a", second_body)

    def invoke(self, capability: str, operation: str, *, token: str, payload: dict | None = None):
        return self.request(
            "POST",
            f"/component-api/v1/capabilities/{capability}/operations/{operation}:invoke",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-GenB-Agent-Credential": "test-agent"},
            data={"schemaVersion": "1.0", "context": {"requestId": f"m0-{operation}", "conversationId": "m0-conversation"}, "payload": payload or {}},
        )

    def request(self, method: str, path: str, *, headers: dict[str, str] | None = None, data: dict | None = None):
        encoded = None if data is None else json.dumps(data).encode("utf-8")
        request = Request(f"{BASE_URL}{path}", method=method, headers=headers or {}, data=encoded)
        try:
            with urlopen(request, timeout=0.5) as response:
                return response.status, response.read().decode("utf-8"), response.headers
        except HTTPError as error:
            return error.code, error.read().decode("utf-8"), error.headers
        except URLError as error:
            self.fail(f"数据面网关尚未实现或未启动，M0预期保持红色：{error.reason}")

    def assert_problem(self, status: int, body: str, content_type, expected_status: int, expected_code: str) -> None:
        self.assertEqual(expected_status, status, body)
        self.assertEqual("application/problem+json", content_type.get_content_type())
        problem = json.loads(body)
        self.assertEqual(expected_code, problem["code"])
        self.assertEqual(expected_status, problem["status"])
        self.assertTrue(problem["requestId"])


if __name__ == "__main__":
    unittest.main()
