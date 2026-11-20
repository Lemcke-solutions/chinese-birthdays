from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.lunar_birthdays.const import DOMAIN

from .common import add_person


async def _start(hass: HomeAssistant, name: str = "Anna", birth_date: str = "1985-01-20"):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": name, "birth_date": birth_date}
    )


async def test_confirm_calculated_lunar_date(hass: HomeAssistant) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    placeholders = result["description_placeholders"]
    assert placeholders["lunar_year"] == "1984"
    assert placeholders["lunar_month"] == "11"
    assert placeholders["lunar_day"] == "30"
    assert placeholders["leap"] == "✗"
    assert placeholders["animal"] == "鼠"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"correct": True})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Anna"
    assert result["data"] == {
        "entry_type": "person",
        "name": "Anna",
        "birth_date": "1985-01-20",
        "lunar_year": 1984,
        "lunar_month": 11,
        "lunar_day": 30,
        "lunar_leap": False,
    }

    # The shared calendar entry is created automatically.
    entries = hass.config_entries.async_entries(DOMAIN)
    assert sorted(e.data["entry_type"] for e in entries) == ["calendar", "person"]
    assert hass.states.get("calendar.lunar_birthdays") is not None


async def test_leap_month_shown(hass: HomeAssistant) -> None:
    result = await _start(hass, birth_date="2023-04-01")
    assert result["description_placeholders"]["leap"] == "✓"


async def test_manual_lunar_date(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"correct": False})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"lunar_year": 1985, "lunar_month": 1, "lunar_day": 3, "lunar_leap": False},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["lunar_year"] == 1985
    assert result["data"]["lunar_month"] == 1
    assert result["data"]["lunar_day"] == 3
    assert result["data"]["birth_date"] == "1985-01-20"


async def test_out_of_range(hass: HomeAssistant) -> None:
    result = await _start(hass, birth_date="1899-12-31")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "out_of_range"}


async def test_duplicate_person(hass: HomeAssistant) -> None:
    await add_person(hass)
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_only_one_calendar(hass: HomeAssistant) -> None:
    await add_person(hass, name="Anna")
    await add_person(hass, name="Bo", birth_date="1990-09-04", year=1990, month=7, day=15)
    calendars = [
        e for e in hass.config_entries.async_entries(DOMAIN) if e.data["entry_type"] == "calendar"
    ]
    assert len(calendars) == 1


async def test_options_flow_changes_zodiac(hass: HomeAssistant) -> None:
    entry = await add_person(hass)
    assert hass.states.get("sensor.anna_chinese_zodiac").state == "rat"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"lunar_year": 1985, "lunar_month": 1, "lunar_day": 1, "lunar_leap": False},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["lunar_year"] == 1985
    # Original calculated value is kept in data.
    assert entry.data["lunar_year"] == 1984

    state = hass.states.get("sensor.anna_chinese_zodiac")
    assert state.state == "ox"
    assert state.attributes["character"] == "牛"
    assert hass.states.get("sensor.anna_next_lunar_birthday").attributes["lunar_date"] == "1-1"


async def test_no_options_for_calendar(hass: HomeAssistant) -> None:
    await add_person(hass)
    calendar = next(
        e for e in hass.config_entries.async_entries(DOMAIN) if e.data["entry_type"] == "calendar"
    )
    assert not calendar.supports_options
