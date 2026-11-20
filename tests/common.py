from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lunar_birthdays.const import DOMAIN


def person_data(name: str = "Anna", birth_date: str = "1985-01-20", year=1984, month=11, day=30, leap=False) -> dict:
    return {
        "entry_type": "person",
        "name": name,
        "birth_date": birth_date,
        "lunar_year": year,
        "lunar_month": month,
        "lunar_day": day,
        "lunar_leap": leap,
    }


async def add_person(hass: HomeAssistant, **kwargs) -> MockConfigEntry:
    data = person_data(**kwargs)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=data["name"],
        data=data,
        unique_id=f"{data['name'].lower()}_{data['birth_date']}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
