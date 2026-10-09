## graphify

This component is part of a larger project. It uses a global knowledge graph located at the workspace root (`../graphify-out/`).

Rules:
- Before answering architecture or codebase questions, read the global report at **`../graphify-out/GRAPH_REPORT.md`** for god nodes and community structure.
- If `../graphify-out/wiki/index.md` exists, navigate it instead of reading raw files.
- For cross-module questions, prefer `graphify query`, `graphify path`, or `graphify explain` (run from root or via MCP) over grep.
- After modifying code files in this session, run `graphify update .` from the **workspace root** to keep the global graph current.
