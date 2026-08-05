"""Final mechanical and independent model-semantic verification specialist."""

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import (
    PolicyDecision,
    PrimaryPolicySelection,
    VerificationIssue,
    VerificationReport,
)
from ecommerce_dispute.tools.validators import verify_case_output

from .base import AgentSpec, BaseAgent
from .policy import compact_policy_facts, policy_decision_is_source_grounded


class VerifierAgent(BaseAgent):
    spec = AgentSpec(
        name="verifier_agent",
        prompt_file=BaseAgent.prompt_path("verifier_agent.md"),
        allowed_tools=(
            "validate_output_schema",
            "verify_arithmetic",
            "verify_evidence",
            "independently_apply_policy",
        ),
    )

    async def run(self, state: CaseState) -> VerificationReport:
        case_id = state.case_input.case_id
        if state.draft_output is None or state.policy_decision is None:
            raise RuntimeError("Verifier Agent requires a draft output and policy decision")
        self.trace("started", case_id)
        mechanical_report = verify_case_output(state, state.draft_output)
        if mechanical_report.status == "fail":
            self.trace(
                "mechanical_verification_failed",
                case_id,
                issues=mechanical_report.model_dump(mode="json")["issues"],
            )
            return mechanical_report

        facts = compact_policy_facts(state)
        primary = await self.decide(
            case_id,
            {
                "task": "Independently select only the first matching EC_POLICY_V2 primary issue.",
                "facts": facts,
                "mechanical_gates": "pass",
            },
            PrimaryPolicySelection,
            max_new_tokens=64,
        )
        expected = await self.decide(
            case_id,
            {
                "task": (
                    "Independently complete every PolicyDecision field for the selected "
                    "primary. The draft is hidden so it cannot anchor your answer."
                ),
                "selected_primary_issue": primary.primary_issue,
                "facts": facts,
                "mechanical_gates": "pass",
            },
            PolicyDecision,
            accept=lambda value: (
                value.primary_issue == primary.primary_issue
                and policy_decision_is_source_grounded(value, facts)
            ),
            rejection_message=(
                "The independent decision must copy selected_primary_issue and use only "
                "source IDs and amounts"
            ),
            max_new_tokens=320,
        )
        actual_values = state.policy_decision.model_dump(mode="json")
        expected_values = expected.model_dump(mode="json")
        semantic_fields = (
            "primary_issue",
            "secondary_issues",
            "case_status",
            "root_cause_codes",
            "responsible_parties",
            "recommended_refund_brl",
            "resolution_actions",
        )
        issues = [
            VerificationIssue(
                field=field,
                code="SEMANTIC_DISAGREEMENT",
                message=f"Verifier expected {expected_value!r}, got {actual_values[field]!r}",
                owner_agent="policy_agent",
                retryable=True,
            )
            for field in semantic_fields
            for expected_value in (expected_values[field],)
            if actual_values[field] != expected_value
        ]
        report = VerificationReport(status="fail" if issues else "pass", issues=issues)
        self.trace(
            "handoff",
            case_id,
            recipient="supervisor_agent",
            payload_type="VerificationReport",
            status=report.status,
            issue_count=len(report.issues),
        )
        return report
