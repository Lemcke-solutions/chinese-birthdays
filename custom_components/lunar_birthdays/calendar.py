from __future__ import annotations

from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import PersonData, get_persons
from .const import SIGNAL_UPDATED
from .lunar_calc import (
    LunarRangeError,
    age_on,
    birthdays_between,
    next_birthday,
    zodiac_character,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LunarBirthdayCalendar(entry)])


def _make_event(entry_id: str, person: PersonData, day: date, age: int) -> CalendarEvent:
    lunar = person.lunar_birth
    return CalendarEvent(
        start=day,
        end=day + timedelta(days=1),
        summary=f"{person.name} ({age})",
        description=f"🌙 {lunar.month}/{lunar.day} · {zodiac_character(lunar.year)}",
        uid=f"{entry_id}_{day.isoformat()}",
    )


class LunarBirthdayCalendar(CalendarEntity):
    """One calendar with the lunar birthdays of all persons as all-day events."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "lunar_birthdays"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self.async_write_ha_state)
        )
        self.async_on_remove(
            async_track_time_change(self.hass, self._midnight_update, hour=0, minute=0, second=5)
        )

    @callback
    def _midnight_update(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next upcoming birthday."""
        today = dt_util.now().date()
        upcoming: list[CalendarEvent] = []
        for entry_id, person in get_persons(self.hass).items():
            try:
                day = next_birthday(person.lunar_birth, today)
            except LunarRangeError:
                continue
            upcoming.append(_make_event(entry_id, person, day, age_on(person.lunar_birth, day)))
        return min(upcoming, key=lambda e: (e.start, e.summary), default=None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start_local = dt_util.as_local(start_date)
        end_local = dt_util.as_local(end_date)
        # An all-day event on day d covers [d, d + 1): it overlaps the range if
        # d >= start day and d < end (rounded up to a whole day).
        first = start_local.date()
        last_exclusive = end_local.date()
        if end_local.time() != time(0):
            last_exclusive += timedelta(days=1)

        events = [
            _make_event(entry_id, person, day, age)
            for entry_id, person in get_persons(hass).items()
            for day, age in birthdays_between(person.lunar_birth, first, last_exclusive)
        ]
        events.sort(key=lambda e: (e.start, e.summary))
        return events
