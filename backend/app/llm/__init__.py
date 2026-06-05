"""Provider-abstracted LLM access. Agents depend on the LLMProvider interface, not a vendor.

Default impl: Anthropic (Claude). OpenAI is a drop-in. Agents request a tier ("strong"/"fast"),
so model choice stays configuration (docs/tech-stack.md, docs/architecture.md §2). Build-plan
Phase 2.
"""
from app.llm.base import LLMProvider, LLMResponse  # noqa: F401
from app.llm.factory import get_provider  # noqa: F401
