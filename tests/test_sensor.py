from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.lunar_birthdays.const import DOMAIN

from .common import add_person


async def test_sensors(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-20 12:00:00+01:00")
    entry = await add_person(hass)

    # Born 1985-01-20 = lunar 1984-11-30; lunar 2026-11-30 = 2027-01-07.
    state = hass.states.get("sensor.anna_next_lunar_birthday")
    assert state.state == "2027-01-07"
    assert state.attributes["device_class"] == "date"
    assert state.attributes["lunar_date"] == "11-30"
    assert state.attributes["lunar_month"] == 11
    assert state.attributes["lunar_day"] == 30
    assert state.attributes["lunar_leap_month"] is False
    assert state.attributes["age"] == 42
    assert state.attributes["birth_year"] == 1985
    assert state.attributes["lunar_birth_year"] == 1984

    assert hass.states.get("sensor.anna_days_until_lunar_birthday").state == "48"

    age = hass.states.get("sensor.anna_age_at_next_lunar_birthday")
    assert age.state == "42"
    assert age.attributes["unit_of_measurement"] == "y"

    zodiac = hass.states.get("sensor.anna_chinese_zodiac")
    assert zodiac.state == "rat"
    assert zodiac.attributes["character"] == "鼠"
    assert zodiac.attributes["element"] == "wood"
    assert zodiac.attributes["lunar_year"] == 1984

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == "Anna"
    registry = er.async_get(hass)
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 4
    assert all(e.device_id == device.id for e in er.async_entries_for_config_entry(registry, entry.entry_id))


async def test_midnight_rollover(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2027-01-06 23:59:00+01:00")
    await add_person(hass)
    assert hass.states.get("sensor.anna_days_until_lunar_birthday").state == "1"

    # Birthday itself: days_until becomes 0 just after midnight.
    freezer.move_to("2027-01-07 00:00:05+01:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("sensor.anna_days_until_lunar_birthday").state == "0"
    assert hass.states.get("sensor.anna_next_lunar_birthday").state == "2027-01-07"

    # Day after: jumps to next lunar year (lunar 2027-11-30 = 2027-12-27).
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("sensor.anna_next_lunar_birthday")
    assert state.state == "2027-12-27"
    assert state.attributes["age"] == 43
    assert hass.states.get("sensor.anna_age_at_next_lunar_birthday").state == "43"


async def test_unload(hass: HomeAssistant) -> None:
    entry = await add_person(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.anna_next_lunar_birthday").state == "unavailable"
