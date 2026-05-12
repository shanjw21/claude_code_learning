# Learn Claude Code -- Progress Tracker

## Project: Rebuild learn-claude-code from scratch
**Source:** https://github.com/shareAI-lab/learn-claude-code
**Started:** 2026-04-03
**Philosophy:** "The Model IS the Agent. You build the harness."

---

## Session Progress

| Session | Topic | Lesson Material | Code | Review |
|---------|-------|:---------------:|:----:|:------:|
| s01 | Agent Loop | skipped | skipped | -- |
| s02 | Tool Dispatch | skipped | skipped | -- |
| s03 | TodoWrite + Session Persistence | done | done | done |
| s04 | Subagents | done | -- | -- |
| s05 | Skills | done | -- | -- |
| s06 | Context Compact | done | -- | -- |
| s07 | Tasks (file-based) | done | -- | -- |
| s08 | Background Tasks | done | -- | -- |
| s09 | Agent Teams | done | -- | -- |
| s10 | Team Protocols | done | -- | -- |
| s11 | Autonomous Agents | done | -- | -- |
| s12 | Worktree + Capstone | done | -- | -- |

---

## Status

**Current phase:** s04 implementation (starting)

**Next step:** Implement `run_subagent()` in s04_subagents.py

---

## S03 Implementation Notes

**Completed components:**
- TOOLS definitions (bash, read_file, write_file, edit_file, todo)
- Tool handlers + dispatch (TOOL_DICT + process_tool_call)
- TodoManager class (update + render with validation)
- SessionStore class (JSONL-based persistence)
- Nag counter (rounds_since_todo + text injection)
- Main loop with session commands (/sessions, /new, /delete)

**Key bugs encountered and resolved:**
- self.items vs items parameter confusion
- dict access vs object dot notation
- Unbound method in TOOL_DICT (needed instance wrapper)
- Dual messages.append (old + new code coexisting)
- String building errors (join misuse, string+int concat)

**Review saved at:** `review/s03_review.md`

---

## Lesson Materials Generated

All files in `lessons/`:
- `s03_lesson_material.md` -- TodoWrite (in-memory task list + nag reminder)
- `s04_lesson_material.md` -- Subagents (fresh context for subtasks)
- `s05_lesson_material.md` -- Skills (on-demand SKILL.md loading)
- `s06_lesson_material.md` -- Context Compact (3-layer compression)
- `s07_lesson_material.md` -- Tasks (file-based task graph with dependencies)
- `s08_lesson_material.md` -- Background Tasks (daemon threads + Queue)
- `s09_lesson_material.md` -- Agent Teams (JSONL mailboxes + MessageBus)
- `s10_lesson_material.md` -- Team Protocols (shutdown + plan approval handshake)
- `s11_lesson_material.md` -- Autonomous Agents (idle-cycle task claiming)
- `s12_lesson_material.md` -- Worktree Isolation + Capstone (s01-s11 combined)

---

## Architecture Overview (for reference)

```
The harness layering:

s01  Agent Loop          --> while(stop_reason=="tool_use"): execute, append, loop
s02  Tool Dispatch       --> {tool_name: handler} map (loop unchanged)
s03  TodoWrite           --> in-memory task list + nag reminder
s04  Subagents           --> fresh messages[] for isolated subtasks
s05  Skills              --> on-demand SKILL.md loading
s06  Context Compact     --> 3-layer compression (micro/auto/manual)
s07  Tasks               --> file-based task graph with dependencies
s08  Background Tasks    --> daemon threads + notification queue
s09  Agent Teams         --> JSONL mailboxes + MessageBus
s10  Team Protocols      --> shutdown + plan approval handshake
s11  Autonomous Agents   --> idle-cycle task claiming
s12  Worktree Isolation  --> per-agent directory isolation
```

---

## Notes

- s01 and s02 skipped (assumed prior knowledge)
- All lesson materials use skeleton code with `___` blanks and `# TODO` comments
- No full solutions provided -- fill in the blanks yourself
- Learning approach: understand "why" first, then implement
