---
name: codex-services-development
description: Develop and validate the codex-services library itself, including booking algorithms, calendar behavior, packaged consumer skills and release artifacts. Use in its source checkout; consumer integrations use the shipped codex-services skill.
---

# codex-services development

## Ownership and navigation

This repository publishes `codex-services` through `pyproject.toml` and `.github/workflows/publish.yml`. Keep development guidance here. Consumer guidance belongs in `src/codex_services/agent_skills/resources/`; do not install that managed copy over this development skill.

Read `.agents/rules/graphify.md` for the library-local `graphify-out/` scope and rebuild command. Use the local report (and wiki when present) for orientation, then inspect the relevant current source and tests: graph edges may be inferred or stale. Cross-library contracts belong in public APIs and the relevant library skills, not a shared workspace graph.

- Booking search: `src/codex_services/booking/slot_master/` and `tests/unit/`, `tests/integration/`; architecture context in `docs/en/architecture/booking_engine.md`.
- Slot arithmetic and provider contracts: `src/codex_services/booking/_shared/`.
- Calendar rendering data: `src/codex_services/calendar/`.
- Skill installation and packaged instructions: `src/codex_services/agent_skills/` and its tests. Treat installed consumer copies and manifests as managed output.

## Contracts that affect changes

- Business engines remain framework-independent. ORM access, persistence, HTTP and application policy belong in consumer adapters, not the booking/calendar engines.
- Preserve the distinction between the dictionary facade (`find_slots`, `find_nearest_slots`) and the typed `ChainFinder` API. Verify actual signatures before adapting examples; resource IDs use `possible_resource_ids` and `resource_id`.
- Booking DTOs derive from `codex-core` BaseDTO. Preserve immutable-model semantics and PII-safe representations; do not add customer payloads to logs.
- Recursive search uses lightweight `_SlotCandidate` instances and creates Pydantic solutions at the result boundary. Avoid moving model validation into the backtracking loop without evidence.
- An enum value is not proof a booking mode is implemented. Check `ChainFinder` guards and tests before documenting support.
- Calendar holiday support is optional (`calendar` extra). Keep the base installation usable without it.
- Skill delivery is explicitly invoked and offline. Changes to update/delete must preserve unrelated consumer content and detect modified managed files; test against an isolated project.

## Verification and release work

Use the configured environment; project commands are `uv run pytest`, `uv run mypy src/`, and `uv run pre-commit run --all-files`. An existing environment can run the equivalent Python modules. Inspect `.github/workflows/ci.yml` for the Python-version unit-test matrix and the subsequent full-suite coverage gate (including integration tests). Coverage is configured with a 90% threshold; report failing or skipped checks honestly.

For packaging or skill payload changes, build with `uv build --no-sources`, inspect wheel and sdist contents, and exercise installation from the wheel outside the source checkout. Check executable examples against the packaged public API and ensure reference links stay inside the shipped payload.

Version comes from Git tags via hatch-vcs. Record pending changes under `CHANGELOG.md` Unreleased; a local dirty-build version is not a release tag. Publishing is triggered by a `v*` tag. Preparing a release does not itself authorize creating/pushing that tag or publishing.

After changes affecting graph inputs, rebuild the local graph using `.agents/rules/graphify.md`. Keep generated graph files out of Git and release artifacts; commit only build rules and instructions. If the graph is missing or rebuilding fails, inspect current sources and report the limitation rather than treating a stale graph as current.
