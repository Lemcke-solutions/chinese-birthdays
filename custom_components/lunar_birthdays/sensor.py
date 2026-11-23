from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import PersonData, sensor_entity_id
from .const import DOMAIN, MANUFACTURER
from .lunar_calc import (
    ZODIAC_ANIMALS,
    LunarRangeError,
    age_on,
    element,
    next_birthday,
    zodiac_animal,
    zodiac_character,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    person: PersonData = entry.runtime_data
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        translation_key="person",
        translation_placeholders={"name": person.name},
        manufacturer=MANUFACTURER,
        model="Lunar Birthday",
        entry_type=DeviceEntryType.SERVICE,
    )
    sensors: list[LunarBirthdaySensorBase] = [
        NextBirthdaySensor(entry, person, device_info),
        DaysUntilSensor(entry, person, device_info),
        NextAgeSensor(entry, person, device_info),
        ZodiacSensor(entry, person, device_info),
    ]
    async_add_entities(sensors)

    async def _midnight_update(_now) -> None:
        for sensor in sensors:
            sensor.async_write_ha_state()

    entry.async_on_unload(
        async_track_time_change(hass, _midnight_update, hour=0, minute=0, second=5)
    )


class LunarBirthdaySensorBase(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, person: PersonData, device_info: DeviceInfo) -> None:
        self._person = person
        self._attr_unique_id = f"{entry.entry_id}_{self.translation_key}"
        # Fixed, language-independent entity id so it is recognisable as ours.
        self.entity_id = sensor_entity_id(person.name, self.translation_key)
        self._attr_device_info = device_info
        self._range_warned = False

    def _next_birthday(self) -> date | None:
        try:
            return next_birthday(self._person.lunar_birth, dt_util.now().date())
        except LunarRangeError:
            if not self._range_warned:
                _LOGGER.warning(
                    "No next lunar birthday for %s: outside supported range (1900-2099)",
                    self._person.name,
                )
                self._range_warned = True
            return None


class NextBirthdaySensor(LunarBirthdaySensorBase):
    _attr_translation_key = "next_birthday"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        return self._next_birthday()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lunar = self._person.lunar_birth
        attrs: dict[str, Any] = {
            "lunar_date": f"{lunar.month}-{lunar.day}",
            "lunar_month": lunar.month,
            "lunar_day": lunar.day,
            "lunar_leap_month": lunar.is_leap,
            "birth_date": self._person.birth_date.isoformat(),
            "birth_year": self._person.birth_date.year,
            "lunar_birth_year": lunar.year,
        }
        if (day := self._next_birthday()) is not None:
            attrs["age"] = age_on(lunar, day)
        if self._person.gender:
            attrs["gender"] = self._person.gender
        return attrs


class DaysUntilSensor(LunarBirthdaySensorBase):
    _attr_translation_key = "days_until"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    @property
    def native_value(self) -> int | None:
        if (day := self._next_birthday()) is None:
            return None
        return (day - dt_util.now().date()).days


class NextAgeSensor(LunarBirthdaySensorBase):
    _attr_translation_key = "next_age"
    _attr_native_unit_of_measurement = UnitOfTime.YEARS

    @property
    def native_value(self) -> int | None:
        if (day := self._next_birthday()) is None:
            return None
        return age_on(self._person.lunar_birth, day)


class ZodiacSensor(LunarBirthdaySensorBase):
    _attr_translation_key = "zodiac"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ZODIAC_ANIMALS

    @property
    def native_value(self) -> str:
        return zodiac_animal(self._person.lunar_birth.year)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lunar_year = self._person.lunar_birth.year
        return {
            "character": zodiac_character(lunar_year),
            "element": element(lunar_year),
            "lunar_year": lunar_year,
        }
