"""Contract test: Medical Risk Agent (build-plan 3.1).

Verifies it produces MedicalConstraints, enforces the inviolable deterministic rules (allergies
merged into excluded_foods, standard disclaimer always present), sends constraint gate-edges to
nutrition + fitness, and emits the right trace events.
"""
from __future__ import annotations

from app.agents.medical_risk import MedicalRiskAgent
from app.core.agent_names import FITNESS, NUTRITION, STANDARD_DISCLAIMER
from app.schemas import MedicalConstraints, MedicalFlag, Severity, TraceEventType
from tests.agent_helpers import FakeLLM, event_types, make_ctx, sample_profile


def _canned_constraints() -> MedicalConstraints:
    # Note: excluded_foods deliberately omits the "peanuts" allergy to prove the merge,
    # and required_disclaimers is empty to prove the standard disclaimer gets added.
    return MedicalConstraints(
        max_added_sugar_g=25.0,
        max_sodium_mg=2000.0,
        min_protein_g_per_kg=1.6,
        excluded_foods=["processed meat"],
        forbidden_movements=["box jumps", "deep squats"],
        max_intensity="moderate (RPE <= 6)",
        flags=[MedicalFlag(condition="knee injury", severity=Severity.hard_limit,
                           rationale="Avoid high-impact loading.")],
    )


async def test_medical_risk_contract():
    profile = sample_profile(allergies=["peanuts"])
    llm = FakeLLM(parsed=_canned_constraints())
    ctx, emitter = make_ctx(profile, llm=llm, tool_names=["web_search"])

    result = await MedicalRiskAgent().run(ctx)
    out = result.output

    # produces the right typed output
    assert isinstance(out, MedicalConstraints)
    # allergy merged into excluded foods (inviolable)
    assert "peanuts" in out.excluded_foods
    assert "processed meat" in out.excluded_foods
    # standard disclaimer always attached
    assert STANDARD_DISCLAIMER in out.required_disclaimers
    # gate edges to both specialists
    recipients = {m.recipient for m in result.messages}
    assert recipients == {NUTRITION, FITNESS}
    assert all(m.intent == "constraint" for m in result.messages)


async def test_medical_risk_emits_trace_events():
    profile = sample_profile(allergies=["peanuts"])
    ctx, emitter = make_ctx(profile, llm=FakeLLM(parsed=_canned_constraints()),
                            tool_names=["web_search"])

    await MedicalRiskAgent().run(ctx)
    types = event_types(emitter)

    assert types[0] == TraceEventType.AGENT_STARTED
    assert types[-1] == TraceEventType.AGENT_COMPLETED
    for required in (TraceEventType.AGENT_INPUT, TraceEventType.AGENT_OUTPUT,
                     TraceEventType.MESSAGE_SENT):
        assert required in types
    # exactly two influence edges (→ nutrition, → fitness)
    assert types.count(TraceEventType.MESSAGE_SENT) == 2
