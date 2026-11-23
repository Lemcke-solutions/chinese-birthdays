# Lunar Birthdays

A Home Assistant custom integration for Chinese lunar birthdays. A lunar birthday is celebrated on the same lunar date every year, which falls on a different Gregorian date each year. This integration calculates that date for every person, shows their Chinese zodiac animal and puts all birthdays in one shared calendar, so you can use calendar triggers in automations.

## Features

- One entry per person, added via the UI.
- Enter the date of birth as a Gregorian date or directly as a lunar date. From a Gregorian date the lunar date is calculated, which you confirm or correct (including the lunar year).
- Per person a device (**Maanverjaardag Anna** / **Lunar birthday Anna**) with four sensors: next lunar birthday, days until it, age at that birthday, and the Chinese zodiac animal.
- One shared calendar **Maanverjaardagen** / **Lunar birthdays** (`calendar.lunar_birthdays`) with all persons as all-day events.
- All entity IDs start with `lunar_birthdays_`, regardless of the Home Assistant language, so they are easy to recognise.
- Recalculates daily just after midnight; no polling.
- English and Dutch translations.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/Lemcke-solutions/chinese-birthdays` as type **Integration**.
2. Install **Lunar Birthdays** and restart Home Assistant.

### Manual

Copy the `custom_components/lunar_birthdays` directory to your HA `config/custom_components/` folder and restart.

## Configuration

**Settings → Devices & services → Add integration → Lunar Birthdays**

1. Enter the name, optionally the gender (male, female, other), and choose whether you enter the date of birth as a **Gregorian date** or a **lunar date**.
2. **Gregorian date**: enter day, month and year. The calculated lunar date (lunar year, month, day, leap month) is shown. Confirm it, or uncheck the box to enter the lunar date yourself.
3. **Lunar date**: enter lunar year, month (1–12), day (1–30) and whether it is a leap month. The Gregorian date of birth is calculated from it. A lunar date that does not exist (a leap month that year does not have, or day 30 in a 29-day month) is rejected.

Repeat for every person. The shared calendar entry **Maanverjaardagen** is created automatically with the first person.

The lunar date and gender can be changed afterwards via **Configure** on the person's entry. The lunar year is editable too, since it determines the zodiac animal.

Supported range: dates of birth from 31 January 1900 up to 2099 (the range of the [lunardate](https://pypi.org/project/lunardate/) library).

## Entities

Entity IDs below are for a person named Anna. They are the same in every language; the friendly names are translated (e.g. *Maanverjaardag Anna Leeftijd*).

| Entity | State |
|---|---|
| `sensor.lunar_birthdays_anna_next_birthday` | Gregorian date of the next lunar birthday (device class `date`) |
| `sensor.lunar_birthdays_anna_days_until` | Days until that date (`0` on the birthday itself) |
| `sensor.lunar_birthdays_anna_next_age` | Age that will be celebrated on the next lunar birthday |
| `sensor.lunar_birthdays_anna_zodiac` | Zodiac animal: `rat`, `ox`, `tiger`, `rabbit`, `dragon`, `snake`, `horse`, `goat`, `monkey`, `rooster`, `dog`, `pig` (translated in the UI) |
| `calendar.lunar_birthdays` | All birthdays as all-day events, summary `Anna (42)` |

### Attributes

**Next lunar birthday**

| Attribute | Description |
|---|---|
| `lunar_date` | Lunar month-day, e.g. `11-30` |
| `lunar_month`, `lunar_day` | Lunar month and day of birth |
| `lunar_leap_month` | Whether the person was born in a leap month |
| `age` | Age that is celebrated on the next birthday |
| `birth_date`, `birth_year` | Gregorian date and year of birth |
| `lunar_birth_year` | Lunar year of birth |
| `gender` | `male`, `female` or `other` (only when set) |

**Chinese zodiac**

| Attribute | Description |
|---|---|
| `character` | Chinese character, e.g. `鼠` |
| `element` | `wood`, `fire`, `earth`, `metal` or `water` |
| `lunar_year` | Lunar year of birth |

## Calculation rules

- The lunar year does not coincide with the Gregorian year. The next birthday is the first date on or after today among the birthdays in lunar years −1, 0 and +1 relative to the current Gregorian year.
- Day 30 does not exist in every lunar month; in that case the birthday falls on day 29.
- Someone born in a leap month celebrates in the regular month with the same number, since a leap month rarely recurs.
- The zodiac animal follows the **lunar** year of birth: `(lunar_year - 4) % 12`, 0 = Rat. Someone born on 20 January 1985 was born before Chinese New Year (20 February 1985), in lunar year 1984, and is therefore a Rat, not an Ox.
- The element follows the last digit of the lunar year: 0/1 metal, 2/3 water, 4/5 wood, 6/7 fire, 8/9 earth.

## Example automations

All-day calendar events start at midnight. The `offset` moves the trigger: `09:00:00` fires at 09:00 on the day itself, `-159:00:00` (7 days minus 9 hours) fires at 09:00 one week before.

```yaml
automation:
  - alias: "Lunar birthday today"
    triggers:
      - trigger: calendar
        event: start
        entity_id: calendar.lunar_birthdays
        offset: "09:00:00"
    actions:
      - action: notify.notify
        data:
          title: "🎂 Lunar birthday today"
          message: "{{ trigger.calendar_event.summary }} celebrates their lunar birthday today!"

  - alias: "Lunar birthday in one week"
    triggers:
      - trigger: calendar
        event: start
        entity_id: calendar.lunar_birthdays
        offset: "-159:00:00"
    actions:
      - action: notify.notify
        data:
          title: "🌙 Lunar birthday next week"
          message: "{{ trigger.calendar_event.summary }} has their lunar birthday on {{ as_datetime(trigger.calendar_event.start).strftime('%d-%m-%Y') }}."
```

### Upgrading from 0.1.4 or earlier

Version 0.1.5 renames existing entity IDs once to the `lunar_birthdays_` scheme (e.g. `sensor.anna_volgende_maanverjaardag` → `sensor.lunar_birthdays_anna_next_birthday`, `calendar.maanverjaardagen` → `calendar.lunar_birthdays`). History is kept. Entity IDs you renamed yourself are left alone. Update automations and dashboards that use the old IDs.

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

The calculations live in `custom_components/lunar_birthdays/lunar_calc.py`, which has no Home Assistant dependencies and is tested separately in `tests/test_lunar_calc.py`.
