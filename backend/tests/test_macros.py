"""Tests for the deterministic macros tool — the reliability backbone (build-plan task 1.1).

These verify the math is exact and safety caps work. Extend as the tool evolves. Run: pytest.
"""
from app.schemas import ActivityLevel, Goal, Sex
from app.tools.macros import calculate_macros, mifflin_st_jeor_bmr


def test_bmr_male_known_value():
    # Mifflin-St Jeor: 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
    assert mifflin_st_jeor_bmr(sex=Sex.male, weight_kg=80, height_cm=180, age=30) == 1780


def test_bmr_female_known_value():
    # 10*60 + 6.25*165 - 5*25 - 161 = 600 + 1031.25 - 125 - 161 = 1345.25
    assert mifflin_st_jeor_bmr(sex=Sex.female, weight_kg=60, height_cm=165, age=25) == 1345.25


def test_tdee_and_deficit_for_fat_loss():
    m = calculate_macros(
        sex=Sex.male, weight_kg=80, height_cm=180, age=30,
        activity_level=ActivityLevel.moderate, goal=Goal.fat_loss,
    )
    # BMR 1780 * 1.55 = 2759 TDEE; fat_loss target must be below TDEE (a deficit).
    assert m.tdee_kcal == 2759
    assert m.target_kcal < m.tdee_kcal


def test_macros_sum_close_to_target():
    m = calculate_macros(
        sex=Sex.male, weight_kg=80, height_cm=180, age=30,
        activity_level=ActivityLevel.moderate, goal=Goal.muscle_gain,
    )
    kcal_from_macros = m.protein_g * 4 + m.carbs_g * 4 + m.fat_g * 9
    # Allow rounding slack from per-gram rounding.
    assert abs(kcal_from_macros - m.target_kcal) <= 30


def test_safety_floor_for_small_female():
    m = calculate_macros(
        sex=Sex.female, weight_kg=45, height_cm=155, age=22,
        activity_level=ActivityLevel.sedentary, goal=Goal.fat_loss,
    )
    assert m.target_kcal >= 1200  # never below the safety floor
