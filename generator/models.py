from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Requirement(StrictModel):
    id: str = Field(pattern=r"^FR-[0-9]{3}$")
    statement: str
    source_quote: str
    acceptance: list[str] = Field(min_length=1)
    priority: Literal["must", "should", "could"]


class Question(StrictModel):
    question: str
    reason: str
    blocking: bool
    proposed_default: str


class Analysis(StrictModel):
    title: str
    purpose: str
    scope: str
    roles: list[str] = Field(min_length=1)
    requirements: list[Requirement] = Field(min_length=1)
    nonfunctional: list[str]
    assumptions: list[str]
    questions: list[Question]
    entities: list[str]
    scenarios: list[str]
    integrations: list[str]
    risks: list[str]


class Endpoint(StrictModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(pattern=r"^/api/v1/")
    purpose: str
    roles: list[str]
    request: str
    response: str
    requirement_ids: list[str] = Field(min_length=1)


class Blueprint(StrictModel):
    product_name: str
    entities: list[str]
    endpoints: list[Endpoint] = Field(min_length=1)
    events: list[str]
    screens: list[str]
    decisions: list[str]
    acceptance_tests: list[str]


class Artifact(StrictModel):
    path: str
    content: str = Field(min_length=1)
    requirement_ids: list[str]


class ArtifactBatch(StrictModel):
    files: list[Artifact] = Field(min_length=1)


class Check(StrictModel):
    name: str
    command: list[str]
    status: Literal["passed", "failed", "not_run"]
    exit_code: int | None
    duration_seconds: float
    log: str


class Evidence(StrictModel):
    requirement_id: str
    files: list[str]
    checks: list[str]
    status: Literal["passed", "failed", "unverified"]


class ReviewIssue(StrictModel):
    severity: Literal["critical", "high", "medium"]
    path: str
    source_quote: str
    requirement_ids: list[str]
    defect: str
    correction: str


class BackendReview(StrictModel):
    passes_static_review: bool
    issues: list[ReviewIssue]
