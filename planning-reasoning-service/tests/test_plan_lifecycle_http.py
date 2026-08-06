from fastapi.testclient import TestClient
import pytest

from planning_reasoning import main as main_module
from planning_reasoning.main import app
from planning_reasoning.plan_lifecycle import InMemoryPlanStore, PlanLifecycle


HEADERS = {
    "X-Tenant-Id": "tenant-plan-a",
    "X-Agent-Id": "agent-plan-a",
    "X-User-Id": "user-plan-a",
    "Idempotency-Key": "idem-plan-create-001",
}


@pytest.fixture(autouse=True)
def isolated_plan_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "plan_lifecycle",
        PlanLifecycle(InMemoryPlanStore()),
    )


def test_plan_can_be_created_and_read_with_pending_steps() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/planning-reasoning/plans",
            headers=HEADERS,
            json={
                "taskId": "task-credit-review",
                "goal": "完成银行对公授信材料检查",
                "steps": [
                    {
                        "title": "核对必需材料",
                        "completionCriteria": "输出缺失材料清单",
                    },
                    {
                        "title": "生成检查报告",
                        "completionCriteria": "报告包含结论和人工复核项",
                    },
                ],
                "maxReplans": 2,
            },
        )

        assert created.status_code == 201
        plan = created.json()["data"]
        loaded = client.get(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}",
            headers=HEADERS,
        )

    assert plan["taskId"] == "task-credit-review"
    assert plan["goal"] == "完成银行对公授信材料检查"
    assert plan["status"] == "ACTIVE"
    assert plan["revision"] == 1
    assert plan["replanCount"] == 0
    assert plan["maxReplans"] == 2
    assert [step["status"] for step in plan["steps"]] == ["PENDING", "PENDING"]
    assert [step["order"] for step in plan["steps"]] == [1, 2]
    assert loaded.status_code == 200
    assert loaded.json()["data"] == plan


def test_plan_creation_replays_the_same_result_for_the_same_idempotency_key() -> None:
    request = {
        "taskId": "task-idempotent-plan",
        "goal": "完成幂等计划",
        "steps": [
            {"title": "检查材料", "completionCriteria": "形成缺失清单"}
        ],
    }
    headers = {**HEADERS, "Idempotency-Key": "idem-plan-create-replay-001"}
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/planning-reasoning/plans", headers=headers, json=request
        )
        replay = client.post(
            "/api/v1/planning-reasoning/plans", headers=headers, json=request
        )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["data"] == first.json()["data"]


def test_first_pending_step_can_be_started() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-start-001"},
            json={
                "taskId": "task-start-step",
                "goal": "执行授信检查",
                "steps": [
                    {"title": "检查材料", "completionCriteria": "形成缺失清单"},
                    {"title": "输出报告", "completionCriteria": "形成报告文件"},
                ],
            },
        ).json()["data"]

        transitioned = client.post(
            f"/api/v1/planning-reasoning/plans/{created['planId']}"
            "/steps/step-1:transition",
            headers=HEADERS,
            json={"targetStatus": "IN_PROGRESS"},
        )

    assert transitioned.status_code == 200
    plan = transitioned.json()["data"]
    assert plan["status"] == "ACTIVE"
    assert [step["status"] for step in plan["steps"]] == ["IN_PROGRESS", "PENDING"]


def test_step_transition_replays_the_same_result_for_the_same_idempotency_key() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-transition-replay-create"},
            json={
                "taskId": "task-transition-replay",
                "goal": "验证步骤转换幂等",
                "steps": [
                    {"title": "执行步骤", "completionCriteria": "步骤完成"}
                ],
            },
        ).json()["data"]
        url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        headers = {**HEADERS, "Idempotency-Key": "idem-transition-replay-001"}
        request = {"targetStatus": "IN_PROGRESS"}

        first = client.post(url, headers=headers, json=request)
        replay = client.post(url, headers=headers, json=request)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]


def test_in_progress_step_can_be_completed() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-complete-001"},
            json={
                "taskId": "task-complete-step",
                "goal": "完成检查计划",
                "steps": [
                    {"title": "检查材料", "completionCriteria": "形成缺失清单"},
                    {"title": "输出报告", "completionCriteria": "形成报告文件"},
                ],
            },
        ).json()["data"]
        transition_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        assert client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-complete-start-001"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200

        completed = client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-complete-finish-001"},
            json={"targetStatus": "COMPLETED"},
        )

    assert completed.status_code == 200
    updated = completed.json()["data"]
    assert updated["status"] == "ACTIVE"
    assert [step["status"] for step in updated["steps"]] == ["COMPLETED", "PENDING"]


def test_failed_step_requires_replanning() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-fail-001"},
            json={
                "taskId": "task-failed-step",
                "goal": "完成检查计划",
                "steps": [
                    {"title": "检查材料", "completionCriteria": "形成缺失清单"}
                ],
            },
        ).json()["data"]
        transition_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        assert client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-failed-start-001"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200

        failed = client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-failed-finish-001"},
            json={"targetStatus": "FAILED"},
        )

    assert failed.status_code == 200
    updated = failed.json()["data"]
    assert updated["status"] == "REPLAN_REQUIRED"
    assert updated["steps"][0]["status"] == "FAILED"


def test_observation_is_appended_without_replacing_history() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-observe-001"},
            json={
                "taskId": "task-observation",
                "goal": "完成检查计划",
                "steps": [
                    {"title": "检查材料", "completionCriteria": "形成缺失清单"}
                ],
            },
        ).json()["data"]
        observation_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}/observations"
        )

        first = client.post(
            observation_url,
            headers={**HEADERS, "Idempotency-Key": "idem-observation-first-001"},
            json={"source": "TOOL", "content": "营业执照有效"},
        )
        second = client.post(
            observation_url,
            headers={**HEADERS, "Idempotency-Key": "idem-observation-second-001"},
            json={"source": "USER", "content": "用户补充了近三个月流水"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    observations = second.json()["data"]["observations"]
    assert [(item["source"], item["content"]) for item in observations] == [
        ("TOOL", "营业执照有效"),
        ("USER", "用户补充了近三个月流水"),
    ]


def test_observation_replay_does_not_append_a_duplicate() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-observe-replay-create-001"},
            json={
                "taskId": "task-observation-replay",
                "goal": "验证观察幂等",
                "steps": [
                    {"title": "观察步骤", "completionCriteria": "记录观察"}
                ],
            },
        ).json()["data"]
        url = f"/api/v1/planning-reasoning/plans/{plan['planId']}/observations"
        headers = {**HEADERS, "Idempotency-Key": "idem-observe-replay-001"}
        request = {"source": "TOOL", "content": "工具返回材料有效"}

        first = client.post(url, headers=headers, json=request)
        replay = client.post(url, headers=headers, json=request)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]
    assert len(replay.json()["data"]["observations"]) == 1


def test_replan_preserves_completed_steps_and_replaces_unfinished_steps() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-replan-create-001"},
            json={
                "taskId": "task-replan",
                "goal": "完成检查计划",
                "steps": [
                    {"title": "核对材料", "completionCriteria": "形成缺失清单"},
                    {"title": "调用外部核验", "completionCriteria": "获得核验结果"},
                ],
                "maxReplans": 2,
            },
        ).json()["data"]
        first_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        second_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-2:transition"
        )
        assert client.post(
            first_url,
            headers={**HEADERS, "Idempotency-Key": "idem-replan-first-start"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200
        assert client.post(
            first_url,
            headers={**HEADERS, "Idempotency-Key": "idem-replan-first-finish"},
            json={"targetStatus": "COMPLETED"},
        ).status_code == 200
        assert client.post(
            second_url,
            headers={**HEADERS, "Idempotency-Key": "idem-replan-second-start"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200
        assert client.post(
            second_url,
            headers={**HEADERS, "Idempotency-Key": "idem-replan-second-fail"},
            json={"targetStatus": "FAILED"},
        ).status_code == 200

        replanned = client.post(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}:replan",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-replan-001"},
            json={
                "reason": "外部核验工具超时",
                "steps": [
                    {"title": "重试外部核验", "completionCriteria": "获得核验结果"},
                    {"title": "转人工复核", "completionCriteria": "记录人工复核结论"},
                ],
            },
        )

    assert replanned.status_code == 200
    updated = replanned.json()["data"]
    assert updated["status"] == "ACTIVE"
    assert updated["revision"] == 2
    assert updated["replanCount"] == 1
    assert [(step["title"], step["status"]) for step in updated["steps"]] == [
        ("核对材料", "COMPLETED"),
        ("重试外部核验", "PENDING"),
        ("转人工复核", "PENDING"),
    ]
    assert [step["order"] for step in updated["steps"]] == [1, 2, 3]


def test_replan_replays_the_same_result_for_the_same_idempotency_key() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-replan-replay-create-001"},
            json={
                "taskId": "task-replan-replay",
                "goal": "验证重规划幂等",
                "steps": [
                    {"title": "失败步骤", "completionCriteria": "步骤完成"}
                ],
            },
        ).json()["data"]
        transition_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        assert client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-replay-fail-start"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200
        assert client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-replay-fail-finish"},
            json={"targetStatus": "FAILED"},
        ).status_code == 200
        replan_url = f"/api/v1/planning-reasoning/plans/{plan['planId']}:replan"
        headers = {**HEADERS, "Idempotency-Key": "idem-replan-replay-001"}
        request = {
            "reason": "外部工具失败",
            "steps": [
                {"title": "替代步骤", "completionCriteria": "步骤完成"}
            ],
        }

        first = client.post(replan_url, headers=headers, json=request)
        replay = client.post(replan_url, headers=headers, json=request)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]
    assert replay.json()["data"]["replanCount"] == 1


def test_cancel_preserves_completed_steps_and_cancels_unfinished_steps() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-cancel-create-001"},
            json={
                "taskId": "task-cancel",
                "goal": "执行后可取消的计划",
                "steps": [
                    {"title": "已完成步骤", "completionCriteria": "步骤完成"},
                    {"title": "待执行步骤", "completionCriteria": "步骤完成"},
                ],
            },
        ).json()["data"]
        first_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        assert client.post(
            first_url,
            headers={**HEADERS, "Idempotency-Key": "idem-cancel-start-001"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200
        assert client.post(
            first_url,
            headers={**HEADERS, "Idempotency-Key": "idem-cancel-finish-001"},
            json={"targetStatus": "COMPLETED"},
        ).status_code == 200

        cancelled = client.post(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}:cancel",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-cancel-001"},
            json={"reason": "用户终止本次检查"},
        )

    assert cancelled.status_code == 200
    updated = cancelled.json()["data"]
    assert updated["status"] == "CANCELLED"
    assert [step["status"] for step in updated["steps"]] == [
        "COMPLETED", "CANCELLED"
    ]


def test_cancel_replays_the_same_result_for_the_same_idempotency_key() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-cancel-replay-create"},
            json={
                "taskId": "task-cancel-replay",
                "goal": "验证取消幂等",
                "steps": [
                    {"title": "待取消步骤", "completionCriteria": "步骤完成"}
                ],
            },
        ).json()["data"]
        url = f"/api/v1/planning-reasoning/plans/{plan['planId']}:cancel"
        headers = {**HEADERS, "Idempotency-Key": "idem-plan-cancel-replay-001"}
        request = {"reason": "用户终止本次计划"}

        first = client.post(url, headers=headers, json=request)
        replay = client.post(url, headers=headers, json=request)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]
    assert len(replay.json()["data"]["observations"]) == 1


def test_terminal_plan_rejects_further_step_transitions() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-terminal-create-001"},
            json={
                "taskId": "task-terminal",
                "goal": "验证计划终态",
                "steps": [
                    {"title": "待取消步骤", "completionCriteria": "步骤完成"}
                ],
            },
        ).json()["data"]
        assert client.post(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}:cancel",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-terminal-cancel-001"},
            json={"reason": "结束测试"},
        ).status_code == 200

        rejected = client.post(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition",
            headers=HEADERS,
            json={"targetStatus": "IN_PROGRESS"},
        )

    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "PLAN_TERMINAL"


def test_plan_is_hidden_from_another_user() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-isolation-001"},
            json={
                "taskId": "task-isolation",
                "goal": "验证计划隔离",
                "steps": [
                    {"title": "隔离步骤", "completionCriteria": "其他用户不可见"}
                ],
            },
        ).json()["data"]

        hidden = client.get(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}",
            headers={**HEADERS, "X-User-Id": "user-plan-b"},
        )

    assert hidden.status_code == 404


def test_replan_limit_returns_stable_conflict() -> None:
    with TestClient(app) as client:
        plan = client.post(
            "/api/v1/planning-reasoning/plans",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-limit-create-001"},
            json={
                "taskId": "task-replan-limit",
                "goal": "验证重规划上限",
                "steps": [
                    {"title": "失败步骤", "completionCriteria": "步骤完成"}
                ],
                "maxReplans": 0,
            },
        ).json()["data"]
        transition_url = (
            f"/api/v1/planning-reasoning/plans/{plan['planId']}"
            "/steps/step-1:transition"
        )
        assert client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-limit-start-001"},
            json={"targetStatus": "IN_PROGRESS"},
        ).status_code == 200
        assert client.post(
            transition_url,
            headers={**HEADERS, "Idempotency-Key": "idem-limit-finish-001"},
            json={"targetStatus": "FAILED"},
        ).status_code == 200

        rejected = client.post(
            f"/api/v1/planning-reasoning/plans/{plan['planId']}:replan",
            headers={**HEADERS, "Idempotency-Key": "idem-plan-limit-replan-001"},
            json={
                "reason": "尝试超额重规划",
                "steps": [
                    {"title": "替代步骤", "completionCriteria": "步骤完成"}
                ],
            },
        )

    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "REPLAN_LIMIT_REACHED"
