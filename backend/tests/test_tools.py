"""Tests for the external-data tools (build-plan 1.2 USDA, 1.3 prices, 1.4 web_search).

These are deterministic and network-free: the happy paths monkeypatch the isolated network
helpers (`_fetch_usda`, `_fetch_tavily`, `web_search`), and the degradation paths assert the
tools fall back gracefully (offline table / seeded prices / empty list) without raising.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.tools import prices, usda, web_search
from app.tools.web_search import SearchResult


# ───────────────────────────── prices (1.3) ───────────────────────────────
def test_seed_table_loaded_and_suffixes_stripped():
    table = prices._seed_table()
    # bare names recovered from suffixed JSON keys
    assert table["milk"] == 60.0              # milk_per_litre
    assert table["gym membership"] == 1500.0  # gym membership_per_month
    assert table["dumbbells"] == 2500.0       # dumbbells_one_time
    assert table["eggs"] == 7.0               # groceries_per_unit
    assert table["chicken breast"] == 250.0   # groceries_per_kg


async def test_prices_seeded_known_item():
    assert await prices.price_of("chicken breast") == (250.0, "seeded")


async def test_prices_substring_match():
    # "chicken" resolves to the seeded "chicken breast"
    cost, source = await prices.price_of("chicken")
    assert (cost, source) == (250.0, "seeded")


async def test_prices_unit_qty_scales():
    cost, source = await prices.price_of("rice", unit_qty=2)
    assert (cost, source) == (120.0, "seeded")


async def test_prices_unknown_item_is_graceful():
    assert await prices.price_of("unobtainium") == (0.0, "seeded")


async def test_live_price_extracts_currency_number(monkeypatch):
    async def fake_search(query, *, max_results=5):
        return [SearchResult("t", "u", "Chicken now sells at ₹280 per kg in the market")]

    monkeypatch.setattr(prices, "web_search", fake_search)
    assert await prices._live_price_lookup("chicken") == (280.0, "web_search")


async def test_price_of_prefers_live_when_not_seeded(monkeypatch):
    monkeypatch.setattr(prices, "get_settings", lambda: SimpleNamespace(use_seeded_prices=False))

    async def fake_live(item):
        return (99.0, "web_search")

    monkeypatch.setattr(prices, "_live_price_lookup", fake_live)
    assert await prices.price_of("anything") == (99.0, "web_search")


async def test_price_of_falls_back_to_seed_when_live_empty(monkeypatch):
    monkeypatch.setattr(prices, "get_settings", lambda: SimpleNamespace(use_seeded_prices=False))

    async def no_live(item):
        return None

    monkeypatch.setattr(prices, "_live_price_lookup", no_live)
    assert await prices.price_of("rice") == (60.0, "seeded")


# ───────────────────────────── usda (1.2) ─────────────────────────────────
def test_usda_fallback_table_scaled():
    item = usda._fallback_food("chicken breast", 200)
    assert item.kcal == 330.0          # 165 * 2
    assert item.protein_g == 62.0      # 31 * 2
    assert item.quantity == "200 g"
    assert item.fdc_id is None         # signals an estimate, not real USDA


def test_usda_fallback_unknown_is_zeroed():
    item = usda._fallback_food("xyzfood", 150)
    assert (item.kcal, item.protein_g, item.carbs_g, item.fat_g) == (0.0, 0.0, 0.0, 0.0)
    assert item.name == "xyzfood"
    assert item.fdc_id is None


def test_usda_extract_macros_from_search_hit():
    food = {
        "fdcId": 999,
        "foodNutrients": [
            {"nutrientNumber": "203", "value": 31.0},
            {"nutrientNumber": "204", "value": 3.6},
            {"nutrientNumber": "205", "value": 0.0},
            {"nutrientNumber": "208", "value": 165.0},
        ],
    }
    macros = usda._extract_macros(food)
    assert macros == {"kcal": 165.0, "protein_g": 31.0, "carbs_g": 0.0, "fat_g": 3.6}


async def test_usda_lookup_uses_api_when_available(monkeypatch):
    usda._cache.clear()

    async def fake_fetch(name):
        return ({"kcal": 165.0, "protein_g": 31.0, "carbs_g": 0.0, "fat_g": 3.6}, 12345)

    monkeypatch.setattr(usda, "_fetch_usda", fake_fetch)
    item = await usda.lookup_food("grilled chicken", 100)
    assert item.kcal == 165.0
    assert item.fdc_id == 12345  # real USDA id flows through


async def test_usda_lookup_degrades_on_error(monkeypatch):
    usda._cache.clear()

    async def boom(name):
        raise RuntimeError("API down")

    monkeypatch.setattr(usda, "_fetch_usda", boom)
    item = await usda.lookup_food("paneer", 100)  # paneer is in the offline table
    assert item.kcal == 265.0
    assert item.fdc_id is None  # fell back to the estimate, no raise


# ─────────────────────────── web_search (1.4) ─────────────────────────────
async def test_web_search_empty_without_key(monkeypatch):
    monkeypatch.setattr(web_search, "get_settings", lambda: SimpleNamespace(tavily_api_key=""))
    assert await web_search.web_search("anything") == []


async def test_web_search_maps_results(monkeypatch):
    monkeypatch.setattr(web_search, "get_settings", lambda: SimpleNamespace(tavily_api_key="x"))

    async def fake_fetch(query, max_results, api_key):
        return [SearchResult("Title", "https://example.com", "snippet text")]

    monkeypatch.setattr(web_search, "_fetch_tavily", fake_fetch)
    results = await web_search.web_search("query")
    assert len(results) == 1
    assert results[0].url == "https://example.com"


async def test_web_search_degrades_on_error(monkeypatch):
    monkeypatch.setattr(web_search, "get_settings", lambda: SimpleNamespace(tavily_api_key="x"))

    async def boom(query, max_results, api_key):
        raise RuntimeError("network down")

    monkeypatch.setattr(web_search, "_fetch_tavily", boom)
    assert await web_search.web_search("query") == []
