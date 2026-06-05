"""Web search tool (Tavily by default) behind a stable interface.

Implements build-plan task 1.4. Used by Medical Risk (guidelines/contraindications), Fitness
(safe alternatives), and Budget (local prices). The provider is swappable; callers depend only
on `web_search(...) -> list[SearchResult]`.

Graceful degradation (docs/architecture.md §6): no key, a timeout, or any error returns an
empty list so the calling agent falls back to model knowledge and notes the assumption — it
must never raise into the agent.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings

_TAVILY_URL = "https://api.tavily.com/search"
_TIMEOUT = 10.0  # seconds


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


async def _fetch_tavily(query: str, max_results: int, api_key: str) -> list[SearchResult]:
    """Call the Tavily search API and map hits to SearchResult.

    Isolated from `web_search` so the degradation path is testable without a network.
    """
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_TAVILY_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    results: list[SearchResult] = []
    for hit in (data.get("results") or [])[:max_results]:
        results.append(
            SearchResult(
                title=str(hit.get("title", "")),
                url=str(hit.get("url", "")),
                snippet=str(hit.get("content", "") or hit.get("snippet", "")),
            )
        )
    return results


async def web_search(query: str, *, max_results: int = 5) -> list[SearchResult]:
    """Return up to `max_results` results for `query`, or [] if search is unavailable.

    Never raises: a missing key, timeout, HTTP error, or malformed payload degrades to [].
    """
    api_key = get_settings().tavily_api_key
    if not api_key:
        return []
    try:
        return await _fetch_tavily(query, max_results, api_key)
    except Exception:
        return []  # timeout / HTTP / parse error → degrade to empty, caller notes assumption
