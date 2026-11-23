from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lunar_birthdays.const import DOMAIN

from .common import person_data


async def test_migrate_entity_ids(hass: HomeAssistant) -> None:
    """Entities created by 0.1.4 and earlier get the lunar_birthdays_ prefix."""
    registry = er.async_get(hass)
    person = MockConfigEntry(
        domain=DOMAIN, title="Anna", data=person_data(), unique_id="anna_1985-01-20", minor_version=1
    )
    calendar = MockConfigEntry(
        domain=DOMAIN, title="Maanverjaardagen", data={"entry_type": "calendar"}, unique_id="calendar", minor_version=1
    )
    person.add_to_hass(hass)
    calendar.add_to_hass(hass)

    def register(platform: str, unique_suffix: str, object_id: str, entry: MockConfigEntry) -> None:
        registry.async_get_or_create(
            platform, DOMAIN, f"{entry.entry_id}_{unique_suffix}",
            suggested_object_id=object_id, config_entry=entry,
        )

    # Dutch installation, plus one sensor the user renamed themselves.
    register("sensor", "next_birthday", "anna_volgende_maanverjaardag", person)
    register("sensor", "days_until", "anna_dagen_tot_maanverjaardag", person)
    register("sensor", "next_age", "anna_leeftijd_bij_volgende_maanverjaardag", person)
    register("sensor", "zodiac", "mijn_eigen_sterrenbeeld", person)
    register("calendar", "calendar", "maanverjaardagen", calendar)

    assert await hass.config_entries.async_setup(person.entry_id)
    await hass.async_block_till_done()

    def entity_id(platform: str, entry: MockConfigEntry, suffix: str) -> str:
        return registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{suffix}")

    assert entity_id("sensor", person, "next_birthday") == "sensor.lunar_birthdays_anna_next_birthday"
    assert entity_id("sensor", person, "days_until") == "sensor.lunar_birthdays_anna_days_until"
    assert entity_id("sensor", person, "next_age") == "sensor.lunar_birthdays_anna_next_age"
    assert entity_id("sensor", person, "zodiac") == "sensor.mijn_eigen_sterrenbeeld"
    assert entity_id("calendar", calendar, "calendar") == "calendar.lunar_birthdays"
    assert person.minor_version == 2
    assert calendar.minor_version == 2
    assert hass.states.get("sensor.lunar_birthdays_anna_next_birthday") is not None
    assert hass.states.get("calendar.lunar_birthdays") is not None


async def test_migrate_english_ids(hass: HomeAssistant) -> None:
    registry = er.async_get(hass)
    person = MockConfigEntry(
        domain=DOMAIN, title="Anna", data=person_data(), unique_id="anna_1985-01-20", minor_version=1
    )
    person.add_to_hass(hass)
    registry.async_get_or_create(
        "sensor", DOMAIN, f"{person.entry_id}_zodiac",
        suggested_object_id="anna_chinese_zodiac", config_entry=person,
    )
    assert await hass.config_entries.async_setup(person.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{person.entry_id}_zodiac") == "sensor.lunar_birthdays_anna_zodiac"
