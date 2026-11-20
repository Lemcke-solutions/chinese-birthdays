"""Lunar birthday calculations.

Pure module: depends only on the standard library and lunardate, so it can be
tested without Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lunardate import LunarDate

MIN_LUNAR_YEAR = 1900
MAX_LUNAR_YEAR = 2099

ZODIAC: list[tuple[str, str]] = [
    ("rat", "鼠"),
    ("ox", "牛"),
    ("tiger", "虎"),
    ("rabbit", "兔"),
    ("dragon", "龙"),
    ("snake", "蛇"),
    ("horse", "马"),
    ("goat", "羊"),
    ("monkey", "猴"),
    ("rooster", "鸡"),
    ("dog", "狗"),
    ("pig", "猪"),
]

ZODIAC_ANIMALS: list[str] = [animal for animal, _ in ZODIAC]

# Indexed by the last digit of the lunar year.
ELEMENTS: list[str] = [
    "metal", "metal", "water", "water", "wood",
    "wood", "fire", "fire", "earth", "earth",
]


class LunarRangeError(ValueError):
    """Raised when a date falls outside the range supported by lunardate."""


@dataclass(frozen=True)
class LunarBirth:
    """A birthday expressed in the Chinese lunar calendar."""

    year: int
    month: int
    day: int
    is_leap: bool = False


def solar_to_lunar(d: date) -> LunarBirth:
    """Convert a Gregorian date to its lunar date."""
    # fromSolarDate does not validate its range and returns nonsense outside
    # it (e.g. day -30), so verify by converting back.
    try:
        lunar = LunarDate.fromSolarDate(d.year, d.month, d.day)
        valid = lunar.toSolarDate() == d
    except (ValueError, IndexError):
        valid = False
    if not valid:
        raise LunarRangeError(f"{d} is outside the supported range")
    return LunarBirth(lunar.year, lunar.month, lunar.day, bool(lunar.isLeapMonth))


def lunar_to_solar(year: int, month: int, day: int) -> date:
    """Gregorian date of a lunar date in the regular (non-leap) month.

    Day 30 does not exist in every lunar month; it falls back to day 29.
    """
    if not MIN_LUNAR_YEAR <= year <= MAX_LUNAR_YEAR:
        raise LunarRangeError(f"Lunar year {year} is outside the supported range")
    try:
        return LunarDate(year, month, day).toSolarDate()
    except ValueError:
        if day != 30:
            raise
        return LunarDate(year, month, 29).toSolarDate()


def birthday_in_lunar_year(birth: LunarBirth, lunar_year: int) -> date:
    """Gregorian date on which the birthday is celebrated in a lunar year.

    Someone born in a leap month celebrates in the regular month with the
    same number, since the leap month rarely recurs.
    """
    return lunar_to_solar(lunar_year, birth.month, birth.day)


def next_birthday(birth: LunarBirth, today: date) -> date:
    """First Gregorian date on or after today on which the birthday falls."""
    candidates = []
    for lunar_year in (today.year - 1, today.year, today.year + 1):
        if lunar_year <= birth.year:
            continue
        try:
            candidates.append(birthday_in_lunar_year(birth, lunar_year))
        except LunarRangeError:
            continue
    upcoming = [d for d in candidates if d >= today]
    if not upcoming:
        raise LunarRangeError(f"No lunar birthday on or after {today} in supported range")
    return min(upcoming)


def celebrated_lunar_year(birth: LunarBirth, celebration: date) -> int:
    """Lunar year in which a celebration date (a birthday) falls."""
    return solar_to_lunar(celebration).year


def age_on(birth: LunarBirth, celebration: date) -> int:
    """Age that is celebrated on a birthday date."""
    return celebrated_lunar_year(birth, celebration) - birth.year


def birthdays_between(birth: LunarBirth, start: date, end: date) -> list[tuple[date, int]]:
    """All birthdays (date, age) with start <= date < end."""
    result = []
    first = max(start.year - 1, birth.year + 1, MIN_LUNAR_YEAR)
    last = min(end.year, MAX_LUNAR_YEAR)
    for lunar_year in range(first, last + 1):
        day = birthday_in_lunar_year(birth, lunar_year)
        if start <= day < end:
            result.append((day, lunar_year - birth.year))
    return result


def zodiac_index(lunar_year: int) -> int:
    """Index into ZODIAC, 0 = Rat."""
    return (lunar_year - 4) % 12


def zodiac_animal(lunar_year: int) -> str:
    return ZODIAC[zodiac_index(lunar_year)][0]


def zodiac_character(lunar_year: int) -> str:
    return ZODIAC[zodiac_index(lunar_year)][1]


def element(lunar_year: int) -> str:
    return ELEMENTS[lunar_year % 10]
