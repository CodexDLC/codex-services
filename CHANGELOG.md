<!-- Type: TRACKING -->

# Changelog


All notable changes to this project will be documented in this file.

## [Unreleased]

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
