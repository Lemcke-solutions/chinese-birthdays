from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from . import get_lunar_birth, is_calendar_entry
from .const import (
    CALENDAR_TITLE,
    CALENDAR_UNIQUE_ID,
    CONF_BIRTH_DATE,
    CONF_ENTRY_TYPE,
    CONF_LUNAR_DAY,
    CONF_LUNAR_LEAP,
    CONF_LUNAR_MONTH,
    CONF_LUNAR_YEAR,
    DOMAIN,
    ENTRY_TYPE_CALENDAR,
    ENTRY_TYPE_PERSON,
)
from .lunar_calc import (
    MAX_LUNAR_YEAR,
    MIN_LUNAR_YEAR,
    LunarBirth,
    LunarRangeError,
    solar_to_lunar,
    zodiac_character,
)

CONF_CORRECT = "correct"


def _number(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX)
    )


def _lunar_schema(lunar: LunarBirth) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LUNAR_YEAR, default=lunar.year): _number(MIN_LUNAR_YEAR, MAX_LUNAR_YEAR),
            vol.Required(CONF_LUNAR_MONTH, default=lunar.month): _number(1, 12),
            vol.Required(CONF_LUNAR_DAY, default=lunar.day): _number(1, 30),
            vol.Required(CONF_LUNAR_LEAP, default=lunar.is_leap): BooleanSelector(),
        }
    )


def _lunar_from_input(user_input: dict[str, Any]) -> LunarBirth:
    return LunarBirth(
        year=int(user_input[CONF_LUNAR_YEAR]),
        month=int(user_input[CONF_LUNAR_MONTH]),
        day=int(user_input[CONF_LUNAR_DAY]),
        is_leap=bool(user_input[CONF_LUNAR_LEAP]),
    )


def _validate_lunar(lunar: LunarBirth) -> dict[str, str]:
    if not (
        MIN_LUNAR_YEAR <= lunar.year <= MAX_LUNAR_YEAR
        and 1 <= lunar.month <= 12
        and 1 <= lunar.day <= 30
    ):
        return {"base": "invalid_lunar_date"}
    return {}


def _lunar_data(lunar: LunarBirth) -> dict[str, Any]:
    return {
        CONF_LUNAR_YEAR: lunar.year,
        CONF_LUNAR_MONTH: lunar.month,
        CONF_LUNAR_DAY: lunar.day,
        CONF_LUNAR_LEAP: lunar.is_leap,
    }


class LunarBirthdaysConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._name: str = ""
        self._birth_date: date | None = None
        self._lunar: LunarBirth | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LunarBirthdaysOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        return not is_calendar_entry(config_entry)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Create the shared calendar entry (started by the first person entry)."""
        await self.async_set_unique_id(CALENDAR_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=CALENDAR_TITLE, data={CONF_ENTRY_TYPE: ENTRY_TYPE_CALENDAR}
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            birth_date = date.fromisoformat(user_input[CONF_BIRTH_DATE])
            try:
                lunar = solar_to_lunar(birth_date)
            except LunarRangeError:
                errors["base"] = "out_of_range"
            else:
                await self.async_set_unique_id(f"{slugify(name)}_{birth_date.isoformat()}")
                self._abort_if_unique_id_configured()
                self._name = name
                self._birth_date = birth_date
                self._lunar = lunar
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): TextSelector(),
                        vol.Required(CONF_BIRTH_DATE): DateSelector(),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._lunar is not None
        if user_input is not None:
            if user_input[CONF_CORRECT]:
                return self._create_person_entry(self._lunar)
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required(CONF_CORRECT, default=True): BooleanSelector()}),
            description_placeholders={
                "name": self._name,
                "birth_date": self._birth_date.isoformat(),
                "lunar_year": str(self._lunar.year),
                "lunar_month": str(self._lunar.month),
                "lunar_day": str(self._lunar.day),
                "leap": "✓" if self._lunar.is_leap else "✗",
                "animal": zodiac_character(self._lunar.year),
            },
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._lunar is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            lunar = _lunar_from_input(user_input)
            errors = _validate_lunar(lunar)
            if not errors:
                return self._create_person_entry(lunar)

        return self.async_show_form(
            step_id="manual",
            data_schema=_lunar_schema(self._lunar),
            description_placeholders={"name": self._name},
            errors=errors,
        )

    def _create_person_entry(self, lunar: LunarBirth) -> ConfigFlowResult:
        assert self._birth_date is not None
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_PERSON,
                CONF_NAME: self._name,
                CONF_BIRTH_DATE: self._birth_date.isoformat(),
                **_lunar_data(lunar),
            },
        )


class LunarBirthdaysOptionsFlow(OptionsFlow):
    """Correct the lunar birth date (including the lunar year) afterwards."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            lunar = _lunar_from_input(user_input)
            errors = _validate_lunar(lunar)
            if not errors:
                return self.async_create_entry(data=_lunar_data(lunar))

        return self.async_show_form(
            step_id="init",
            data_schema=_lunar_schema(get_lunar_birth(self.config_entry)),
            description_placeholders={"name": self.config_entry.title},
            errors=errors,
        )
