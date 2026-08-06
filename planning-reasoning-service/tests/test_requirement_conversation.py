from planning_reasoning.models import (
    ClarificationQuestion,
    RequirementConversationResult,
    RequirementDraft,
)
from planning_reasoning.repository import InMemoryRequirementDraftRepository
from planning_reasoning.service import RequirementConversationService


class ContextAwareAnalyst:
    def analyze(self, *, previous, message, references, service_token, request_id):
        del references, service_token, request_id
        if previous is None:
            assert message == "帮我生成一个授信材料检查Skill"
            return RequirementConversationResult(
                status="CLARIFYING",
                complexity="SIMPLE",
                draft=RequirementDraft(
                    name="授信材料检查",
                    description="检查授信申请材料是否完整并输出结果",
                    goal="检查授信申请材料",
                ),
                questions=[
                    ClarificationQuestion(
                        questionId="q-inputs",
                        field="expectedInputs",
                        topic="INPUT",
                        question="需要检查哪些授信申请材料？",
                        reason="材料范围会决定检查步骤。",
                        inputHint="例如：授信申请表、营业执照和财务报表。",
                    )
                ],
                decisionSummary="已确认授信材料检查目标，继续确认材料范围。",
            )
        assert previous.goal == "检查授信申请材料"
        assert message == "需要申请表和营业执照"
        return RequirementConversationResult(
            status="CLARIFYING",
            complexity="SIMPLE",
            draft=previous.model_copy(
                update={"expected_inputs": ["授信申请表", "营业执照"]}
            ),
            questions=[
                ClarificationQuestion(
                    questionId="q-outputs",
                    field="expectedOutputs",
                    topic="OUTPUT",
                    question="检查完成后希望得到什么结果？",
                    reason="需要明确Skill的完成标准。",
                    inputHint="例如：缺失材料清单和检查结论。",
                )
            ],
            decisionSummary="已记录申请表和营业执照，不再重复询问材料。",
        )


def test_same_task_accumulates_confirmed_requirements_across_sessions() -> None:
    service = RequirementConversationService(
        repository=InMemoryRequirementDraftRepository(),
        analyst=ContextAwareAnalyst(),
    )

    first = service.converse(
        task_id="task-credit",
        session_id="session-one",
        message="帮我生成一个授信材料检查Skill",
        tenant_id="tenant-a",
        agent_id="agent-a",
        user_id="user-a",
    )
    second = service.converse(
        task_id="task-credit",
        session_id="session-two",
        message="需要申请表和营业执照",
        tenant_id="tenant-a",
        agent_id="agent-a",
        user_id="user-a",
    )

    assert first.questions[0].question_id == "q-inputs"
    assert second.draft.goal == "检查授信申请材料"
    assert second.draft.expected_inputs == ["授信申请表", "营业执照"]
    assert [question.question_id for question in second.questions] == ["q-outputs"]


def test_unanswered_question_is_represented_instead_of_failing_the_conversation() -> None:
    class RepeatingAnalyst:
        def analyze(self, *, previous, **_kwargs):
            return RequirementConversationResult(
                status="CLARIFYING",
                complexity="SIMPLE",
                draft=previous or RequirementDraft(
                    name="材料检查", description="检查业务材料并输出清单", goal="检查材料"
                ),
                questions=[ClarificationQuestion(
                    questionId="q-rule", field="constraints", topic="RULE",
                    question="材料检查依据哪一版制度？", reason="需要确认规则来源。",
                )],
                decisionSummary="仍需确认检查规则。",
            )

    service = RequirementConversationService(
        repository=InMemoryRequirementDraftRepository(), analyst=RepeatingAnalyst()
    )
    first = service.converse(
        task_id="task-repeat", session_id="s1", message="生成材料检查Skill",
        tenant_id="t", agent_id="a", user_id="u",
    )
    second = service.converse(
        task_id="task-repeat", session_id="s2", message="我暂时还不知道",
        tenant_id="t", agent_id="a", user_id="u",
    )

    assert first.questions[0].question_id == "q-rule"
    assert second.questions[0].question_id == "q-rule"
