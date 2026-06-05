"""USDA FoodData Central client — real food/nutrient lookups for the Nutrition Agent.

Implements build-plan task 1.2. API: https://fdc.nal.usda.gov/api-guide.html
(key in Settings.usda_fdc_api_key; the public "DEMO_KEY" works but is rate-limited).

Design rules (docs/architecture.md §2): typed signature, in-run caching, and **graceful
degradation** — a timeout, error, missing key, or empty result must NEVER raise into the
agent. Instead we fall back to a small offline nutrient table (common foods, per 100 g) and,
failing that, a zeroed FoodItem the agent can note as a degradation. A populated `fdc_id`
signals real USDA data; `fdc_id is None` signals the offline/fallback estimate.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.schemas import FoodItem

_FDC_BASE = "https://api.nal.usda.gov/fdc/v1"
_TIMEOUT = 8.0  # seconds — keep a live demo snappy; fall back on slow APIs

# USDA nutrient numbers (stable identifiers across datasets).
_N_PROTEIN = "203"
_N_FAT = "204"
_N_CARBS = "205"
# Energy in kcal: 208 (general), with 957/958 (Atwater specific/general) as fallbacks.
_N_ENERGY = ("208", "957", "958")

# Offline fallback: representative macros per 100 g for foods common in our diet plans.
# Used when the API is unreachable / unconfigured. Approximate, clearly an estimate.
_FALLBACK_NUTRIENTS: dict[str, dict[str, float]] = {
    "chicken breast": {"kcal": 165, "protein_g": 31.0, "carbs_g": 0.0, "fat_g": 3.6},
    "egg": {"kcal": 143, "protein_g": 12.6, "carbs_g": 0.7, "fat_g": 9.5},
    "eggs": {"kcal": 143, "protein_g": 12.6, "carbs_g": 0.7, "fat_g": 9.5},
    "white rice": {"kcal": 130, "protein_g": 2.7, "carbs_g": 28.0, "fat_g": 0.3},
    "rice": {"kcal": 130, "protein_g": 2.7, "carbs_g": 28.0, "fat_g": 0.3},
    "brown rice": {"kcal": 123, "protein_g": 2.7, "carbs_g": 25.6, "fat_g": 1.0},
    "lentils": {"kcal": 116, "protein_g": 9.0, "carbs_g": 20.0, "fat_g": 0.4},
    "tofu": {"kcal": 144, "protein_g": 17.3, "carbs_g": 2.8, "fat_g": 8.7},
    "paneer": {"kcal": 265, "protein_g": 18.3, "carbs_g": 1.2, "fat_g": 20.8},
    "whey protein": {"kcal": 400, "protein_g": 80.0, "carbs_g": 8.0, "fat_g": 7.0},
    "oats": {"kcal": 379, "protein_g": 13.2, "carbs_g": 67.7, "fat_g": 6.5},
    "milk": {"kcal": 60, "protein_g": 3.2, "carbs_g": 4.8, "fat_g": 3.3},
    "spinach": {"kcal": 23, "protein_g": 2.9, "carbs_g": 3.6, "fat_g": 0.4},
    "broccoli": {"kcal": 34, "protein_g": 2.8, "carbs_g": 6.6, "fat_g": 0.4},
    "banana": {"kcal": 89, "protein_g": 1.1, "carbs_g": 22.8, "fat_g": 0.3},
    "peanut butter": {"kcal": 588, "protein_g": 25.1, "carbs_g": 20.0, "fat_g": 50.4},
}

# In-run cache so the same food isn't fetched twice. Keyed by (name, quantity_g).
_cache: dict[tuple[str, float], FoodItem] = {}


def _scale(
    per_100g: dict[str, float], quantity_g: float, *, name: str, fdc_id: int | None
) -> FoodItem:
    """Scale per-100 g macros to `quantity_g` and build a FoodItem."""
    factor = quantity_g / 100.0
    return FoodItem(
        name=name,
        quantity=f"{quantity_g:g} g",
        kcal=round(per_100g.get("kcal", 0.0) * factor, 1),
        protein_g=round(per_100g.get("protein_g", 0.0) * factor, 1),
        carbs_g=round(per_100g.get("carbs_g", 0.0) * factor, 1),
        fat_g=round(per_100g.get("fat_g", 0.0) * factor, 1),
        fdc_id=fdc_id,
    )


def _extract_macros(food: dict) -> dict[str, float]:
    """Pull per-100 g kcal/protein/carbs/fat out of a USDA `foods` search hit."""
    by_number: dict[str, dict] = {}
    for n in food.get("foodNutrients", []):
        num = str(n.get("nutrientNumber") or n.get("number") or "")
        if num:
            by_number[num] = n

    def val(*nums: str) -> float:
        for num in nums:
            n = by_number.get(num)
            if n:
                return float(n.get("value") or n.get("amount") or 0.0)
        return 0.0

    return {
        "kcal": val(*_N_ENERGY),
        "protein_g": val(_N_PROTEIN),
        "carbs_g": val(_N_CARBS),
        "fat_g": val(_N_FAT),
    }


async def _fetch_usda(name: str) -> tuple[dict[str, float], int] | None:
    """Query USDA FoodData Central; return (per-100 g macros, fdc_id) for the best hit.

    Returns None on missing key, network/HTTP error, or no usable result — callers fall back.
    Foundation entries in the search response sometimes omit proximate macros, so we prefer
    SR Legacy / Survey (FNDDS) datasets and pick the first hit that actually reports energy.
    Isolated from `lookup_food` so the fallback path is unit-testable without a network.
    """
    api_key = get_settings().usda_fdc_api_key
    if not api_key:
        return None
    params = {
        "query": name,
        "api_key": api_key,
        "pageSize": 5,
        "dataType": "SR Legacy,Survey (FNDDS),Foundation",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_FDC_BASE}/foods/search", params=params)
        resp.raise_for_status()
        foods = resp.json().get("foods") or []
    for food in foods:
        macros = _extract_macros(food)
        if macros["kcal"] > 0:  # skip entries whose search payload omits proximates
            return macros, int(food.get("fdcId") or 0) or None
    return None


def _fallback_food(name: str, quantity_g: float) -> FoodItem:
    """Offline estimate: use the local nutrient table, else a zeroed FoodItem (no fdc_id)."""
    per_100g = _FALLBACK_NUTRIENTS.get(name.strip().lower(), {})
    return _scale(per_100g, quantity_g, name=name, fdc_id=None)


async def lookup_food(name: str, quantity_g: float = 100.0) -> FoodItem:
    """Return a FoodItem with macros for `name` at `quantity_g` grams.

    Tries USDA first (real `fdc_id`), then an offline table, then zeros — never raises.
    Results are cached per (name, quantity) for the duration of the process.
    """
    cache_key = (name.strip().lower(), round(quantity_g, 1))
    if cache_key in _cache:
        return _cache[cache_key]

    item: FoodItem
    try:
        fetched = await _fetch_usda(name)
    except Exception:
        fetched = None  # timeout / HTTP / parse error → degrade gracefully

    if fetched is not None:
        per_100g, fdc_id = fetched
        item = _scale(per_100g, quantity_g, name=name, fdc_id=fdc_id)
    else:
        item = _fallback_food(name, quantity_g)

    _cache[cache_key] = item
    return item
