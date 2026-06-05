"""Grocery/equipment price lookup for the Budget Agent.

Implements build-plan task 1.3. A real price feed where configured; otherwise a deterministic
**seeded** table loaded from `data/seed_prices.json` (honoring `USE_SEEDED_PRICES`). Every
result records its `source` so the trace shows real-vs-seeded.

Graceful degradation: a live lookup that errors or finds nothing falls back to the seeded
table; an unknown item returns 0.0 (the Budget Agent notes it) — this tool never raises.
Unit/amortization (e.g. one-time equipment → weekly cost) is the Budget Agent's job, not here.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.tools.web_search import web_search

# data/seed_prices.json lives at backend/data/ (app/tools -> app -> backend).
_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed_prices.json"

# Unit suffixes baked into the JSON keys; stripped to recover the bare item name.
_UNIT_SUFFIXES = ("_per_kg", "_per_unit", "_per_litre", "_per_month", "_one_time")

# Inline fallback used only if the JSON file is missing/unreadable (per-kg / per-unit).
_INLINE_SEED: dict[str, float] = {
    "chicken breast": 250.0, "eggs": 7.0, "rice": 60.0, "lentils": 120.0, "tofu": 200.0,
    "paneer": 350.0, "whey protein": 2000.0, "oats": 90.0, "milk": 60.0,
    "gym membership": 1500.0, "dumbbells": 2500.0,
}


def _strip_suffix(key: str) -> str:
    for suffix in _UNIT_SUFFIXES:
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    return key.replace("_", " ").strip().lower()


@lru_cache(maxsize=1)
def _seed_table() -> dict[str, float]:
    """Flatten data/seed_prices.json into {normalized item name: unit price}. Cached."""
    try:
        raw = json.loads(_SEED_PATH.read_text())
    except (OSError, ValueError):
        return dict(_INLINE_SEED)
    table: dict[str, float] = {}
    for _section, entries in raw.items():
        if not isinstance(entries, dict):
            continue  # skip "_comment", "currency", etc.
        for key, price in entries.items():
            if isinstance(price, (int, float)):
                table[_strip_suffix(key)] = float(price)
    return table or dict(_INLINE_SEED)


def _normalize(item: str) -> str:
    return re.sub(r"\s+", " ", item.strip().lower())


def _seeded_price(item: str) -> float | None:
    """Look up `item` in the seed table by exact then substring match. None if absent."""
    table = _seed_table()
    key = _normalize(item)
    if key in table:
        return table[key]
    # substring match either direction ("chicken" ↔ "chicken breast")
    for name, price in table.items():
        if name in key or key in name:
            return price
    return None


async def _live_price_lookup(item: str) -> tuple[float, str] | None:
    """Best-effort live price via web search; parse the first currency-looking number.

    Returns (unit_price, "web_search") or None on no result/parse failure/error.
    """
    try:
        results = await web_search(f"{item} price per kg India", max_results=3)
    except Exception:
        return None
    for r in results:
        m = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)", r.snippet, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "")), "web_search"
            except ValueError:
                continue
    return None


async def price_of(item: str, *, unit_qty: float = 1.0) -> tuple[float, str]:
    """Return (cost, source) for `item` × `unit_qty`. source ∈ {seeded, web_search}.

    Seeded mode (default, demo-safe) uses the local table. Otherwise a live lookup is tried
    first and falls back to seeded, then to 0.0. Never raises.
    """
    settings = get_settings()
    seeded = _seeded_price(item)

    if not settings.use_seeded_prices:
        live = await _live_price_lookup(item)
        if live is not None:
            price, source = live
            return round(price * unit_qty, 2), source

    if seeded is not None:
        return round(seeded * unit_qty, 2), "seeded"
    return 0.0, "seeded"  # unknown item — Budget Agent flags it; don't raise
