"""Real capabilities agents can call: deterministic macros, USDA food data, prices, web search.

Tool design rules (docs/architecture.md §2, docs/contributing.md §B):
  - typed signature + docstring
  - graceful degradation (timeout -> typed fallback) so a flaky API never breaks a demo
  - math is deterministic code, never the LLM
"""
