from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import slugify

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

_LOGGER = logging.getLogger(__name__)

CALENDAR_ENTITY_ID = f"calendar.{DOMAIN}"

# Entity names (en, nl) used before config entry version 1.2 (integration
# 0.1.5), from which HA derived the entity ids. Used to recognise ids that the user did not rename.
_LEGACY_NAMES: dict[str, tuple[str, ...]] = {
    "next_birthday": ("Next lunar birthday", "Volgende maanverjaardag"),
    "days_until": ("Days until lunar birthday", "Dagen tot maanverjaardag"),
    "next_age": ("Age at next lunar birthday", "Leeftijd bij volgende maanverjaardag"),
    "zodiac": ("Chinese zodiac", "Chinees sterrenbeeld"),
}
_LEGACY_CALENDAR_IDS = ("calendar.lunar_birthdays", "calendar.maanverjaardagen")


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


def sensor_entity_id(name: str, key: str) -> str:
    return f"sensor.{DOMAIN}_{slugify(name)}_{key}"


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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        await _async_migrate_entity_ids(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename entity ids to the fixed lunar_birthdays_ prefix.

    Only ids that HA generated from the old names are renamed; ids the user
    renamed themselves are left alone.
    """
    registry = er.async_get(hass)
    renames: dict[str, str] = {}
    if is_calendar_entry(entry):
        renames = {old: CALENDAR_ENTITY_ID for old in _LEGACY_CALENDAR_IDS}
    else:
        name = entry.data[CONF_NAME]
        for key, legacy_names in _LEGACY_NAMES.items():
            for legacy in legacy_names:
                renames[f"sensor.{slugify(f'{name} {legacy}')}"] = sensor_entity_id(name, key)

    @callback
    def _update(reg_entry: er.RegistryEntry) -> dict[str, str] | None:
        new_id = renames.get(reg_entry.entity_id)
        if new_id is None or new_id == reg_entry.entity_id:
            return None
        if registry.async_get(new_id) is not None:
            _LOGGER.warning("Cannot rename %s to %s: already in use", reg_entry.entity_id, new_id)
            return None
        _LOGGER.info("Renaming %s to %s", reg_entry.entity_id, new_id)
        return {"new_entity_id": new_id}

    await er.async_migrate_entries(hass, entry.entry_id, _update)


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
