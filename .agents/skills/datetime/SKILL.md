---
name: datetime
description: Use when a task needs the current date or time, for example to date a doc, a learnings entry or a spec, to compute how long until or since something, or to convert a time between timezones. Do not guess the date from memory.
---

# datetime

Prints the current date and time in the requested format and timezone.

> Status: planned. The `npm run datetime` script does not exist yet. The options below are the intended interface and must be implemented in the script before this skill is used.

## Command

```bash
npm run datetime -- [options]
```

With no options it prints the current date and time in ISO 8601 with the UTC offset, in the machine's timezone.

## Options

| Option | Meaning |
|--------|---------|
| `--tz <IANA name>` | Timezone, for example `Europe/Helsinki` or `UTC` |
| `--format <name>` | `iso` (default), `date` (`YYYY-MM-DD`), `time` (`HH:mm`), `unix` (seconds), or `human` (for example `Tue 20 Oct 2026 17:50`) |
| `--json` | Print all formats and the timezone as JSON |

## Requirements

- Node.js and the project dependencies installed.
- No network access or API key. The script reads the system clock.

## Rules

- Use this skill instead of writing a date from memory. Use it for the "Last reviewed" date in `docs/content-plan.md`, spec `Created` dates, and `docs/learnings.md` entries.
- State the timezone when it matters. The default for this project is the user's timezone, `Europe/Helsinki`, unless told otherwise.
- The result is only as accurate as the system clock. If a date looks wrong, say so and ask.

## Examples

Current time, ISO 8601:

```bash
npm run datetime
```

Today's date for a doc, in the user's timezone:

```bash
npm run datetime -- --tz Europe/Helsinki --format date
```

All formats as JSON, in UTC:

```bash
npm run datetime -- --tz UTC --json
```
