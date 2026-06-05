"""Canonical agent registry names — defined once, used everywhere.

These strings are the registry keys, the `sender`/`recipient` on AgentMessages, the
`target_agents` on Conflicts/RevisionRequests, and the UI node ids. Per docs/contributing.md
(Conventions): define them once, don't scatter string literals.
"""
from __future__ import annotations

MEDICAL_RISK = "medical_risk"
NUTRITION = "nutrition"
FITNESS = "fitness"
BUDGET = "budget"
CRITIC = "critic"
RESOLVER = "resolver"

# Standard disclaimer the Medical Risk Agent always attaches and the Resolver surfaces.
STANDARD_DISCLAIMER = (
    "This plan is informational and not medical advice. Consult a qualified healthcare "
    "professional before changing your diet, medication, or exercise routine."
)
