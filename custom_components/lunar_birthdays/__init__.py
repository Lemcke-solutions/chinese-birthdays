from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CALENDAR_UNIQUE_ID,
    CONF_BIRTH_DATE,
    CONF_ENTRY_TYPE,
    CONF_LUNAR_DAY,
    CONF_LUNAR_LEAP,
    CONF_LUNAR_MONTH,
    CONF_LUNAR_YEAR,
    DOMAIN,
    ENTRY_TYPE_CALENDAR,
    SIGNAL_UPDATED,
)
from .lunar_calc import LunarBirth


@dataclass(frozen=True)
class PersonData:
    name: str
    birth_date: date
    lunar_birth: LunarBirth


def is_calendar_entry(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_CALENDAR


def get_lunar_birth(entry: ConfigEntry) -> LunarBirth:
    """Lunar birth date of a person entry; corrections in options take precedence."""
    source = entry.options if CONF_LUNAR_YEAR in entry.options else entry.data
    return LunarBirth(
        year=int(source[CONF_LUNAR_YEAR]),
        month=int(source[CONF_LUNAR_MONTH]),
        day=int(source[CONF_LUNAR_DAY]),
        is_leap=bool(source.get(CONF_LUNAR_LEAP, False)),
    )


def get_persons(hass: HomeAssistant) -> dict[str, PersonData]:
    """All currently loaded persons, keyed by config entry id."""
    return hass.data.setdefault(DOMAIN, {})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if is_calendar_entry(entry):
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.CALENDAR])
        return True

    person = PersonData(
        name=entry.data[CONF_NAME],
        birth_date=date.fromisoformat(entry.data[CONF_BIRTH_DATE]),
        lunar_birth=get_lunar_birth(entry),
    )
    entry.runtime_data = person
    get_persons(hass)[entry.entry_id] = person

    if hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, CALENDAR_UNIQUE_ID) is None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data={})
        )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_dispatcher_send(hass, SIGNAL_UPDATED)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if is_calendar_entry(entry):
        return await hass.config_entries.async_unload_platforms(entry, [Platform.CALENDAR])

    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    if unloaded:
        get_persons(hass).pop(entry.entry_id, None)
        async_dispatcher_send(hass, SIGNAL_UPDATED)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
