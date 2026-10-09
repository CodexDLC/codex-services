# codex-services
<!-- Type: LANDING -->

[![PyPI version](https://img.shields.io/pypi/v/codex-services.svg)](https://pypi.org/project/codex-services/)
[![Python](https://img.shields.io/pypi/pyversions/codex-services.svg)](https://pypi.org/project/codex-services/)
[![CI](https://github.com/codexdlc/codex-services/actions/workflows/ci.yml/badge.svg)](https://github.com/codexdlc/codex-services/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

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

### Local code graph

For source-checkout navigation, install Graphify separately and run from this repository root:

```bash
graphify update .
```

This builds an AST-only code graph in `graphify-out/`, using `.graphifyignore` to exclude environments, caches, and generated outputs. It does not use the parent workspace graph or an LLM API. Read documentation and skills directly for explanations beyond the code structure; this command does not perform semantic documentation extraction or generate a wiki.

The graph is generated local data and is not committed or shipped in releases. Commit only `.graphifyignore` and the build instructions. See [.agents/rules/graphify.md](.agents/rules/graphify.md) for navigation and refresh rules.

## Quick Start

```python
from codex_services.booking.slot_master import find_slots

result = find_slots(
    request_data={
        "booking_date": "2026-10-12",
        "service_requests": [
            {"service_id": "haircut", "duration_minutes": 60, "possible_resource_ids": ["m1"]},
        ],
    },
    resources_availability=[
        {"resource_id": "m1", "free_windows": [["2026-10-12T09:00:00", "2026-10-12T11:00:00"]]},
    ],
)
for chain in result["solutions"]:
    print(chain["items"][0]["start_time"])
```

## Optional agent skill

Starting with **0.1.4**, the package includes an optional skill that helps coding agents use its booking, slot arithmetic, and calendar APIs. The skill is bundled with the library; no separate plugin or download is needed.

From the root of a consuming project, using the Python environment where `codex-services` is installed:

```bash
python -m codex_services.agent_skills install --project .
python -m codex_services.agent_skills status --project .
```

`install` copies the versioned guide to `.agents/skills/codex-services` and adds a scoped instruction to the project's `AGENTS.md`. The installer stores file hashes in `.manifest.json`; `update` and `delete` refuse to replace locally edited managed files. Put local rules in a separate project-owned skill. The installer preserves unrelated files and `AGENTS.md` content, and no skill is installed as part of importing or installing the package.

After upgrading the Python package, refresh the project's skill with `python -m codex_services.agent_skills update --project .`. To remove the managed skill, use `python -m codex_services.agent_skills delete --project .`.

See the [agent skill guide](docs/en/agent_skills.md) for paths with spaces, status checks, updates, and local-edit recovery.

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
