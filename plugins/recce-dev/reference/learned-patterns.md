# Learned Patterns

Cross-project patterns accumulated during recce-dev operations.

Curate periodically and PR valuable entries back to the origin repo.

---

### [2026-03-22] Forge — Plugin agents in skill subdirectories are not auto-discovered

**Pattern**: Agent `.md` files placed in `skills/<name>/agents/` instead of the plugin root `agents/` directory are not registered in Claude Code's subagent type registry. Dispatching via `Agent` tool with `subagent_type: "plugin:agent-name"` fails with "agent type not found". The agent must be dispatched as a general-purpose agent with the full rubric inlined in the prompt.
**Applies to**: Any plugin with agents defined inside skill subdirectories
**Action**: Place agents in plugin root `agents/` for auto-discovery, or document that skill-scoped agents require manual dispatch with inlined instructions
