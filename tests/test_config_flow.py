from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.lunar_birthdays.const import DOMAIN

from .common import add_person


async def _choose(hass: HomeAssistant, name: str, calendar_type: str, gender: str | None = None):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    user_input = {"name": name, "calendar_type": calendar_type}
    if gender is not None:
        user_input["gender"] = gender
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == calendar_type
    return result


async def _start(hass: HomeAssistant, name: str = "Anna", birth_date: str = "1985-01-20"):
    result = await _choose(hass, name, "gregorian")
    year, month, day = (int(part) for part in birth_date.split("-"))
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"birth_day": day, "birth_month": str(month), "birth_year": year},
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
    result = await _start(hass, birth_date="1900-01-30")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gregorian"
    assert result["errors"] == {"base": "out_of_range"}


async def test_invalid_date(hass: HomeAssistant) -> None:
    result = await _start(hass, birth_date="1985-02-30")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gregorian"
    assert result["errors"] == {"base": "invalid_date"}


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
    assert hass.states.get("sensor.lunar_birthdays_anna_zodiac").state == "rat"

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

    state = hass.states.get("sensor.lunar_birthdays_anna_zodiac")
    assert state.state == "ox"
    assert state.attributes["character"] == "牛"
    assert hass.states.get("sensor.lunar_birthdays_anna_next_birthday").attributes["lunar_date"] == "1-1"


async def test_no_options_for_calendar(hass: HomeAssistant) -> None:
    await add_person(hass)
    calendar = next(
        e for e in hass.config_entries.async_entries(DOMAIN) if e.data["entry_type"] == "calendar"
    )
    assert not calendar.supports_options


async def _enter_lunar(hass: HomeAssistant, year: int, month: int, day: int, leap: bool = False, name: str = "Anna"):
    result = await _choose(hass, name, "lunar")
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"lunar_year": year, "lunar_month": month, "lunar_day": day, "lunar_leap": leap},
    )


async def test_lunar_input(hass: HomeAssistant) -> None:
    result = await _enter_lunar(hass, 1984, 11, 30)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entry_type": "person",
        "name": "Anna",
        "birth_date": "1985-01-20",
        "lunar_year": 1984,
        "lunar_month": 11,
        "lunar_day": 30,
        "lunar_leap": False,
    }
    assert hass.states.get("sensor.lunar_birthdays_anna_zodiac").state == "rat"


async def test_lunar_input_leap_month(hass: HomeAssistant) -> None:
    result = await _enter_lunar(hass, 2023, 2, 11, leap=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["birth_date"] == "2023-04-01"
    assert result["data"]["lunar_leap"] is True


async def test_lunar_input_regular_month(hass: HomeAssistant) -> None:
    result = await _enter_lunar(hass, 2023, 2, 11, leap=False)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["birth_date"] == "2023-03-02"


async def test_lunar_input_not_found(hass: HomeAssistant) -> None:
    # 2024 has no leap month 2.
    result = await _enter_lunar(hass, 2024, 2, 1, leap=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "lunar"
    assert result["errors"] == {"base": "lunar_date_not_found"}


async def test_lunar_input_day_30_not_found(hass: HomeAssistant) -> None:
    # Month 2 of 2026 has only 29 days.
    result = await _enter_lunar(hass, 2026, 2, 30)
    assert result["errors"] == {"base": "lunar_date_not_found"}


async def test_lunar_input_duplicate(hass: HomeAssistant) -> None:
    await add_person(hass)
    result = await _enter_lunar(hass, 1984, 11, 30)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_gender_gregorian(hass: HomeAssistant) -> None:
    result = await _choose(hass, "Anna", "gregorian", gender="female")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"birth_day": 20, "birth_month": "1", "birth_year": 1985}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"correct": True})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["gender"] == "female"
    state = hass.states.get("sensor.lunar_birthdays_anna_next_birthday")
    assert state.attributes["gender"] == "female"


async def test_gender_lunar(hass: HomeAssistant) -> None:
    result = await _choose(hass, "Bo", "lunar", gender="male")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"lunar_year": 1990, "lunar_month": 8, "lunar_day": 15, "lunar_leap": False},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["gender"] == "male"


async def test_gender_optional(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"correct": True})
    await hass.async_block_till_done()
    assert "gender" not in result["data"]
    state = hass.states.get("sensor.lunar_birthdays_anna_next_birthday")
    assert "gender" not in state.attributes


async def test_options_flow_gender(hass: HomeAssistant) -> None:
    """Gender can be added to an existing person and removed again."""
    entry = await add_person(hass)
    lunar = {"lunar_year": 1984, "lunar_month": 11, "lunar_day": 30, "lunar_leap": False}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**lunar, "gender": "other"}
    )
    await hass.async_block_till_done()
    assert entry.options["gender"] == "other"
    state = hass.states.get("sensor.lunar_birthdays_anna_next_birthday")
    assert state.attributes["gender"] == "other"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], lunar)
    await hass.async_block_till_done()
    assert "gender" not in entry.options
    state = hass.states.get("sensor.lunar_birthdays_anna_next_birthday")
    assert "gender" not in state.attributes
