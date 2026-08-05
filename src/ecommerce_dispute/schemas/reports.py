"""Mechanical, semantic and run-level reporting contracts."""

from typing import Literal

from pydantic import Field, model_validator

from .common import StrictModel


class ValidationIssue(StrictModel):
    field: str
    code: str
    message: str
    owner_component: str | None = None
    retryable: bool = False


class MechanicalReport(StrictModel):
    status: Literal["pass", "fail"]
    issues: list[ValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_issues(self) -> "MechanicalReport":
        if (self.status == "pass") == bool(self.issues):
            raise ValueError("pass requires no issues and fail requires at least one issue")
        return self


class VerificationReport(StrictModel):
    status: Literal["pass", "disagree"]
    issues: list[ValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_issues(self) -> "VerificationReport":
        if (self.status == "pass") == bool(self.issues):
            raise ValueError("pass requires no issues and disagree requires at least one issue")
        return self


class CaseManifestEntry(StrictModel):
    case_id: str
    status: Literal["success", "failed", "needs_review"]
    phase: str
    output_path: str | None = None
    error: str | None = None


class RunManifest(StrictModel):
    run_id: str
    status: Literal["success", "partial_failure", "needs_review"]
    cases_total: int = Field(ge=0)
    cases_succeeded: int = Field(ge=0)
    cases_failed: int = Field(ge=0)
    cases_needing_review: int = Field(ge=0)
    cases: list[CaseManifestEntry]
