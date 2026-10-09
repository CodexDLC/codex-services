## Project skills

For development of this library, read `.agents/skills/codex-services-development/SKILL.md`.
Consumer usage guidance is maintained separately in `src/codex_services/agent_skills/resources/`
and shipped with the library; do not replace the development skill with an installed consumer copy.

## graphify

This library owns its local graph in `graphify-out/`. Follow `.agents/rules/graphify.md`
for scope, navigation, and rebuilding. Graph commands run from this repository root,
not the parent workspace. The generated graph is ignored by Git.
