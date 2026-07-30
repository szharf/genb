from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16_000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class ToolReference(BaseModel):
    protocol: Literal["MCP", "HTTP_API", "SDK"]
    server: ShortText
    tool: ShortText
    purpose: ShortText


class RequirementRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    goal: NonBlankText
    expected_inputs: list[ShortText] = Field(default_factory=list, alias="expectedInputs", max_length=50)
    expected_outputs: list[ShortText] = Field(default_factory=list, alias="expectedOutputs", max_length=50)
    constraints: list[ShortText] = Field(default_factory=list, max_length=50)
    preferred_tools: list[ShortText] = Field(default_factory=list, alias="preferredTools", max_length=50)
    tool_references: list[ToolReference] = Field(default_factory=list, alias="toolReferences", max_length=50)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(default="LOW", alias="riskLevel")


class ClarificationQuestion(BaseModel):
    field: Literal["goal", "expectedInputs", "expectedOutputs", "constraints"]
    question: str
    required: bool = True


class RequirementAnalysis(BaseModel):
    status: Literal["NEEDS_CLARIFICATION", "READY"]
    complexity: Literal["SIMPLE", "COMPLEX"]
    normalized_goal: str = Field(alias="normalizedGoal")
    questions: list[ClarificationQuestion]
    decision_summary: str = Field(alias="decisionSummary")


class RequirementAnalysisResponse(BaseModel):
    data: RequirementAnalysis


class SkillGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: ShortText
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1024)]
    requirements: RequirementRequest


class ValidationIssue(BaseModel):
    code: str
    message: str


class SkillValidation(BaseModel):
    valid: bool
    issues: list[ValidationIssue]


class SkillValidationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    skill_markdown: Annotated[str, StringConstraints(min_length=1, max_length=100_000)] = Field(alias="skillMarkdown")
    require_mcp: bool = Field(default=False, alias="requireMcp")


class SkillValidationResponse(BaseModel):
    data: SkillValidation


class SkillArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    skill_id: str = Field(alias="skillId")
    version: int
    name: str
    complexity: Literal["SIMPLE", "COMPLEX"]
    status: Literal["DRAFT"] = "DRAFT"
    skill_markdown: str = Field(alias="skillMarkdown")
    decision_summary: str = Field(alias="decisionSummary")
    validation: SkillValidation
    created_at: datetime = Field(alias="createdAt")


class SkillArtifactResponse(BaseModel):
    data: SkillArtifact


class FailureEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    failed_step: ShortText = Field(alias="failedStep")
    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128, pattern=r"^[A-Z0-9_:-]+$")] = Field(alias="errorCode")
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]


class SkillReviseRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    base_version: int = Field(alias="baseVersion", ge=1)
    failure: FailureEvent
    adjustment_goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)] = Field(alias="adjustmentGoal")
