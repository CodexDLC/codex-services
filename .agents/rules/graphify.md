## Local code graph

This repository uses only its own `graphify-out/`. It does not depend on the parent workspace graph.

- Before architecture or code-navigation work, read `graphify-out/GRAPH_REPORT.md` when available. If a local `graphify-out/wiki/index.md` exists, use it as an additional entrypoint; native code updates do not generate a wiki.
- Follow `.graphifyignore` to keep environments, caches, build outputs, generated documentation sites, and graph output out of the corpus. Never run the update from the parent workspace for work on this library.
- Build or refresh with `graphify update .` from this repository root, using the separately installed Graphify tool. This is an AST-only code update, with no LLM/API calls. Documentation may be counted in corpus detection but is not semantically extracted by this command; consult source documentation and skills directly.
- For relationships within this library, use `graphify query`, `graphify path`, or `graphify explain` from this repository root when they help. Verify inferred relationships against current code. For cross-library contracts, consult public APIs and the relevant library skills.
- After changing code or graph exclusions, refresh the local graph. If no graph exists or the tool fails, inspect current source and report the missing/stale graph; do not silently fall back to a shared graph.
- `graphify-out/` is generated local data, ignored by Git and excluded from release artifacts. Commit `.graphifyignore` and these instructions, not graph JSON, reports, HTML, wiki pages, caches, or machine-specific interpreter paths.
