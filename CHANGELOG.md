<!-- Type: TRACKING -->

# Changelog


All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.2] - 2026-03-29

### Added
- **Development tooling**:
  - Added `.python-version` for a consistent local Python baseline.
  - Added committed `uv.lock` for reproducible dependency resolution in CI, docs, and local development.
  - Adopted the new `BaseCheckRunner` stage flags so project quality-gate policy is declared through the shared `codex-core` runner contract.
- **README**:
  - Documented the Python 3.12+ requirement and the recommended `uv` development workflow.

### Changed
- **Python baseline**:
  - Raised the minimum supported Python version to `3.12`.
  - Updated static analysis targets (`ruff`, `mypy`) to Python 3.12.
- **CI / Docs / Publish pipelines**:
  - Migrated GitHub Actions workflows to `uv`.
  - Updated the PyPI publish workflow to use the correct `codex-services` project URL.
- **Core dependency**:
  - Updated the supported `codex-core` dependency range to `>=0.2.0,<0.3.0` to align with the shared quality-gate runner behavior across the current `0.2.x` line.
- **Booking modes**:
  - Simplified `BookingMode` to use the standard library `StrEnum` directly now that Python 3.12 is required.

### Fixed
- **Security checks**:
  - Configured the project quality runner to ignore `CVE-2026-4539` for `pygments` because no upstream fix is available yet.

## [0.1.1] - 2026-03-20

### Added
- **Core Library Architecture**: Initial split from monolithic `codex_tools` repository.
- **CRM Booking Engine** (`codex_services.crm.booking`):
  - Unified API for availability and reservations.
  - Multi-mode support: `STRICT`, `FLEXIBLE`, and `OVERBOOK`.
  - Interfaces and algorithms for finding overlapping or chained slots (`chain_finder`, `scorer`).
  - Validation engines for business constraints (`validators`).
  - Strict immutable DTOs and custom exceptions.
- **CRM Calculator Engine** (`codex_services.crm.calculator`):
  - `SlotCalculator` for dynamically analyzing duration and capacity based on business constraints.
- **CRM Calendar Engine** (`codex_services.crm.calendar`):
  - Complete engine for shift generation, schedule building, and timezone-aware recurring events.
- **Documentation**:
  - Implemented standard 6-layer `DocArchitect` layout (API, Architecture, Tasks, Evolution, Landing, Planning).
  - Structured API reference using `mkdocstrings`.
  - Multi-language support structure designed (en/ru).
