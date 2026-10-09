# Optional agent skill

Starting with version **0.1.4**, `codex-services` ships a versioned, offline skill for coding agents covering booking chains, slot arithmetic, and calendar grids. Installing the Python package does not change your project files. Run the command explicitly from the environment where the package is installed:

```bash
python -m codex_services.agent_skills install --project /path/to/project
python -m codex_services.agent_skills status --project /path/to/project
python -m codex_services.agent_skills update --project /path/to/project
python -m codex_services.agent_skills delete --project /path/to/project
```

The guide lives at `.agents/skills/codex-services/SKILL.md` in the consumer project. The installer adds one marked instruction to `AGENTS.md` and records the package version and SHA-256 hashes in `.manifest.json`. `status` reports missing or edited files and whether the payload matches the installed package. `update` requires an existing managed installation and refuses to overwrite local edits; `delete` likewise refuses to discard edited managed files. Both preserve unrelated files and the rest of `AGENTS.md`.

Keep project-specific business rules and integrations in a separate project-owned skill. The copied library guide and its manifest are managed outputs. Restore edited managed files or move custom notes to a project-owned file before running `update` or `delete` again.

## Project paths and discovery

Use `--project .` when running from the consuming project's root. The target directory must already exist. Quote paths containing spaces, for example `--project "D:/Projects/My App"` on Windows. The installer does not install a global skill or modify the agent's global configuration.

Agents that read project `AGENTS.md` or discover `.agents/skills/` can find the installed guide. Agents with different discovery conventions may need to be pointed at `.agents/skills/codex-services/SKILL.md` explicitly.

## Upgrading and checking

Upgrade the Python package with your project's normal dependency manager, then run:

```bash
python -m codex_services.agent_skills update --project .
python -m codex_services.agent_skills status --project .
```

The refresh uses only resources bundled with the installed package and does not access the network. `status` exits with code 0 only when the managed installation matches that package. Exit code 1 means it is absent, outdated, edited, corrupt, or could not be checked; read the accompanying message before acting. On a project without the skill, use `install` rather than `update`.

If an update or deletion is refused, keep a copy of your changes outside the managed directory, move application-specific instructions into a project-owned skill, and restore the original managed content before retrying. Do not edit the manifest hashes to bypass the check. Deleting the skill does not uninstall the Python package.
