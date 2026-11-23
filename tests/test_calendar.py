from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from .common import add_person

ENTITY_ID = "calendar.lunar_birthdays"


async def _get_events(hass: HomeAssistant, start: str, end: str) -> list[dict]:
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": ENTITY_ID, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return response[ENTITY_ID]["events"]


async def test_events_two_years(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-20 12:00:00+01:00")
    await add_person(hass)
    # Lunar 1990-08-15 (mid-autumn).
    bo = await add_person(hass, name="Bo", birth_date="1990-10-03", year=1990, month=8, day=15)

    events = await _get_events(hass, "2026-01-01T00:00:00+01:00", "2028-01-01T00:00:00+01:00")
    assert [(e["start"], e["end"], e["summary"]) for e in events] == [
        ("2026-01-18", "2026-01-19", "Anna (41)"),
        ("2026-09-25", "2026-09-26", "Bo (36)"),
        ("2027-01-07", "2027-01-08", "Anna (42)"),
        ("2027-09-15", "2027-09-16", "Bo (37)"),
        ("2027-12-27", "2027-12-28", "Anna (43)"),
    ]

    state = hass.states.get(ENTITY_ID)
    assert state.state == "off"
    assert state.attributes["message"] == "Anna (42)"
    assert state.attributes["start_time"] == "2027-01-07 00:00:00"
    assert state.attributes["all_day"] is True

    # Removing a person removes their events.
    assert await hass.config_entries.async_unload(bo.entry_id)
    await hass.async_block_till_done()
    events = await _get_events(hass, "2026-01-01T00:00:00+01:00", "2028-01-01T00:00:00+01:00")
    assert {e["summary"] for e in events} == {"Anna (41)", "Anna (42)", "Anna (43)"}


async def test_event_on_birthday(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2027-01-07 10:00:00+01:00")
    await add_person(hass)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "on"
    assert state.attributes["message"] == "Anna (42)"


async def test_range_edges(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-20 12:00:00+01:00")
    await add_person(hass)
    # Range ending exactly at the start of the birthday excludes it.
    assert await _get_events(hass, "2027-01-01T00:00:00+01:00", "2027-01-07T00:00:00+01:00") == []
    # Range that only covers part of the day includes it.
    events = await _get_events(hass, "2027-01-07T18:00:00+01:00", "2027-01-07T19:00:00+01:00")
    assert [e["summary"] for e in events] == ["Anna (42)"]


async def test_dutch_entity_ids(hass: HomeAssistant) -> None:
    hass.config.language = "nl"
    await add_person(hass)
    assert hass.states.get("calendar.maanverjaardagen") is not None
    assert hass.states.get("sensor.anna_volgende_maanverjaardag") is not None
    assert hass.states.get("sensor.anna_chinees_sterrenbeeld").state == "rat"
    assert hass.states.get("sensor.anna_leeftijd_bij_volgende_maanverjaardag") is not None
