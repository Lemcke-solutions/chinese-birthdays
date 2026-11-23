from datetime import date

import pytest

from custom_components.lunar_birthdays.lunar_calc import (
    LunarBirth,
    LunarRangeError,
    age_on,
    birthdays_between,
    element,
    lunar_birth_to_solar,
    lunar_to_solar,
    next_birthday,
    solar_to_lunar,
    zodiac_animal,
    zodiac_character,
)


@pytest.mark.parametrize(
    ("solar", "expected"),
    [
        (date(1985, 1, 20), LunarBirth(1984, 11, 30)),
        (date(1985, 2, 19), LunarBirth(1984, 12, 30)),
        (date(1985, 2, 20), LunarBirth(1985, 1, 1)),
        (date(2026, 2, 16), LunarBirth(2025, 12, 29)),
        (date(2026, 2, 17), LunarBirth(2026, 1, 1)),
        (date(2023, 4, 1), LunarBirth(2023, 2, 11, is_leap=True)),
        (date(1900, 1, 31), LunarBirth(1900, 1, 1)),
    ],
)
def test_solar_to_lunar(solar, expected):
    assert solar_to_lunar(solar) == expected


@pytest.mark.parametrize(
    ("solar", "animal", "character", "elem"),
    [
        # Before Chinese New Year 1985 (Feb 20) still lunar year 1984: Rat, not Ox.
        (date(1985, 1, 20), "rat", "鼠", "wood"),
        (date(1985, 2, 19), "rat", "鼠", "wood"),
        (date(1985, 2, 20), "ox", "牛", "wood"),
        (date(2026, 2, 16), "snake", "蛇", "wood"),
        (date(2026, 2, 17), "horse", "马", "fire"),
        (date(2000, 1, 15), "rabbit", "兔", "earth"),
        (date(2000, 2, 5), "dragon", "龙", "metal"),
    ],
)
def test_zodiac_uses_lunar_year(solar, animal, character, elem):
    lunar_year = solar_to_lunar(solar).year
    assert zodiac_animal(lunar_year) == animal
    assert zodiac_character(lunar_year) == character
    assert element(lunar_year) == elem


@pytest.mark.parametrize(
    ("year", "elem"),
    [(2020, "metal"), (2022, "water"), (2024, "wood"), (2026, "fire"), (2028, "earth"), (2029, "earth")],
)
def test_element_by_last_digit(year, elem):
    assert element(year) == elem


@pytest.mark.parametrize(
    "solar", [date(1899, 12, 31), date(1900, 1, 30), date(2100, 2, 9), date(2100, 6, 1)]
)
def test_solar_out_of_range(solar):
    with pytest.raises(LunarRangeError):
        solar_to_lunar(solar)


def test_lunar_out_of_range():
    with pytest.raises(LunarRangeError):
        lunar_to_solar(1899, 1, 1)
    with pytest.raises(LunarRangeError):
        lunar_to_solar(2100, 1, 1)


def test_day_30_falls_back_to_29():
    # Month 2 has 30 days in 1990 but only 29 in 2026.
    birth = LunarBirth(1990, 2, 30)
    assert lunar_to_solar(2026, 2, 30) == lunar_to_solar(2026, 2, 29)
    assert next_birthday(birth, date(2026, 1, 1)) == lunar_to_solar(2026, 2, 29)
    # Month 2 has 30 days in 2027.
    assert next_birthday(birth, date(2026, 11, 20)) == lunar_to_solar(2027, 2, 30)
    assert lunar_to_solar(2027, 2, 30) != lunar_to_solar(2027, 2, 29)


def test_leap_month_birthday_celebrated_in_regular_month():
    birth = solar_to_lunar(date(2023, 4, 1))
    assert birth == LunarBirth(2023, 2, 11, is_leap=True)
    # Regular month 2 of 2023 precedes the birth; the first birthday is in
    # regular month 2 of 2024.
    assert next_birthday(birth, date(2023, 3, 1)) == lunar_to_solar(2024, 2, 11)
    assert next_birthday(birth, date(2026, 1, 1)) == date(2026, 3, 29)


def test_next_birthday_new_year():
    assert next_birthday(LunarBirth(1990, 1, 1), date(2026, 11, 20)) == date(2027, 2, 6)


def test_next_birthday_year_boundary():
    # Lunar month 12 of lunar year 2025 falls in February 2026, not in 2027.
    assert next_birthday(LunarBirth(1990, 12, 15), date(2026, 1, 10)) == date(2026, 2, 2)


def test_next_birthday_before_chinese_new_year_birth():
    # Born 20 Jan 1985 = lunar 1984-11-30.
    birth = solar_to_lunar(date(1985, 1, 20))
    day = next_birthday(birth, date(2026, 11, 20))
    assert day == lunar_to_solar(2026, 11, 30)
    assert day.year == 2027
    assert age_on(birth, day) == 42


def test_next_birthday_today_counts():
    birth = LunarBirth(1990, 8, 15)
    today = lunar_to_solar(2026, 8, 15)
    assert next_birthday(birth, today) == today
    assert next_birthday(birth, date.fromordinal(today.toordinal() + 1)) == lunar_to_solar(2027, 8, 15)


def test_next_birthday_end_of_range():
    with pytest.raises(LunarRangeError):
        next_birthday(LunarBirth(1990, 1, 1), date(2099, 12, 31))
    # Lunar 2099-12-29 is still in range (in 2100).
    assert next_birthday(LunarBirth(1990, 12, 29), date(2099, 12, 31)) == date(2100, 2, 7)


def test_age_on():
    birth = LunarBirth(1990, 8, 15)
    assert age_on(birth, date(2026, 9, 25)) == 36


def test_birthdays_between():
    birth = LunarBirth(1990, 8, 15)
    assert birthdays_between(birth, date(2026, 1, 1), date(2028, 1, 1)) == [
        (date(2026, 9, 25), 36),
        (date(2027, 9, 15), 37),
    ]


def test_birthdays_between_year_boundary():
    # Month 12 birthdays of lunar year 2025 fall in 2026.
    birth = LunarBirth(1990, 12, 15)
    events = birthdays_between(birth, date(2026, 1, 1), date(2027, 1, 1))
    assert events == [(date(2026, 2, 2), 35)]


def test_birthdays_between_not_before_birth():
    # The day of birth itself is not a birthday.
    birth = LunarBirth(2026, 1, 1)
    assert birthdays_between(birth, date(2025, 1, 1), date(2028, 1, 1)) == [(date(2027, 2, 6), 1)]
    assert next_birthday(birth, date(2026, 2, 17)) == date(2027, 2, 6)


def test_lunar_birth_to_solar():
    assert lunar_birth_to_solar(LunarBirth(1984, 11, 30)) == date(1985, 1, 20)
    assert lunar_birth_to_solar(LunarBirth(2023, 2, 11, is_leap=True)) == date(2023, 4, 1)
    assert lunar_birth_to_solar(LunarBirth(2023, 2, 11)) == date(2023, 3, 2)


def test_lunar_birth_to_solar_no_fallback():
    with pytest.raises(ValueError):
        lunar_birth_to_solar(LunarBirth(2024, 2, 1, is_leap=True))
    with pytest.raises(ValueError):
        lunar_birth_to_solar(LunarBirth(2026, 2, 30))
    with pytest.raises(LunarRangeError):
        lunar_birth_to_solar(LunarBirth(1899, 1, 1))
