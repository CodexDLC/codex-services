---
name: codex-services
description: Use when integrating the codex-services Python library for booking slot search, slot arithmetic, or calendar grids. Skip for application-only business rules and unrelated services.
---

# codex-services consumer guide

Use the installed `codex-services` package as the authority for behavior and version: `python -m pip show codex-services`. The package ships pure Python booking logic and an optional calendar engine. Confirm the installed API before changing an application adapter, especially across package upgrades.

Read only the relevant reference:

- [Booking chains](references/booking.md) for `find_slots`, typed requests, availability, and nearest-day search.
- [Slot windows](references/slot-windows.md) for low-level time arithmetic.
- [Calendar grids](references/calendar.md) for UI calendar data and the `calendar` extra.

Keep database access, tenant authorization, persistence, and framework rendering in the consuming application. Supply the library with validated IDs and time windows; recheck availability and permissions before committing a booking. The managed copy under `.agents/skills/codex-services` and its `.manifest.json` are installer output. Put application-specific guidance in a separate project-owned skill; update this copy through `python -m codex_services.agent_skills update --project <root>`.
