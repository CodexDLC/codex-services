# codex-services
<!-- Type: LANDING -->

[![PyPI version](https://img.shields.io/pypi/v/codex-services.svg)](https://pypi.org/project/codex-services/)
[![Python](https://img.shields.io/pypi/pyversions/codex-services.svg)](https://pypi.org/project/codex-services/)
[![CI](https://github.com/codexdlc/codex-services/actions/workflows/ci.yml/badge.svg)](https://github.com/codexdlc/codex-services/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Pure-Python business logic engines for booking, scheduling, and CRM workflows.
No ORM, no framework dependencies — drop into any Python project or use as a building block inside the Codex ecosystem.

---

## Install

```bash
pip install codex-services

# With holiday calendar support
pip install "codex-services[calendar]"
```

Requires Python 3.12 or newer.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
uv run pre-commit run --all-files
uv build --no-sources
```

## Quick Start

```python
from codex_services.booking.slot_master import find_slots, BookingEngineRequest, ServiceRequest, BookingMode
from datetime import date

request = BookingEngineRequest(
    service_requests=[
        ServiceRequest(service_id="haircut", duration_minutes=60, possible_master_ids=["m1", "m2"]),
    ],
    booking_date=date.today(),
    mode=BookingMode.SINGLE_DAY,
)

result = find_slots(request, masters_availability=[...])
if result.has_solutions:
    print(result.best.starts_at)
```

## Modules

| Module | Extra | Description |
| :--- | :--- | :--- |
| `codex_services.booking.slot_master` | — | Recursive chain-finder for multi-service bookings with scoring and waitlist |
| `codex_services.booking._shared` | — | Low-level slot arithmetic — windows, gaps, busy interval merging |
| `codex_services.calendar` | `[calendar]` | Calendar grid generator for UI rendering with holiday awareness |

## Documentation

Full docs with architecture, API reference, and data flow diagrams:

**[https://codexdlc.github.io/codex-services/](https://codexdlc.github.io/codex-services/)**

## Part of the Codex ecosystem

| Package | Role |
| :--- | :--- |
| [codex-core](https://github.com/codexdlc/codex-core) | Foundation — immutable DTOs, PII masking, env settings |
| [codex-platform](https://github.com/codexdlc/codex-platform) | Infrastructure — Redis, Streams, ARQ workers, Notifications |
| [codex-ai](https://github.com/codexdlc/codex-ai) | LLM layer — unified async interface for OpenAI, Gemini, Anthropic |
| **codex-services** | Business logic — Booking engine, CRM, Calendar |

Each library is **fully standalone** — install only what your project needs.
Together they form the backbone of **[codex-bot](https://github.com/codexdlc/codex-bot)**
(Telegram AI-agent infrastructure built on aiogram) and
**[codex-django](https://github.com/codexdlc/codex-django)** (Django integration layer).
