# S12: Worktree Isolation + Capstone -- "Put it all together"

---

## 1. What Problem Does This Solve?

When multiple agents work in the same directory, they interfere:
- Agent A writes `main.py`, Agent B overwrites it
- Two agents edit the same file simultaneously
- Build artifacts from one agent confuse another

**Worktree isolation gives each agent its own working directory.**

This session is also the **capstone** -- you merge s01 through s11 into a single
`s_full.py` that combines all mechanisms.

---

## 2. Mental Model

```
Before s12:
  All agents share WORKDIR/
  agent_a writes main.py
  agent_b writes main.py  <-- conflict!

After s12:
  WORKDIR/
    .worktrees/
      alice/
        main.py           <-- alice works here
        test_main.py
      bob/
        main.py           <-- bob works here
        README.md
    .tasks/                <-- shared task board
    .team/                 <-- shared team config
    .transcripts/          <-- shared transcripts
    skills/                <-- shared skills

Each agent's tools resolve paths relative to its own worktree.
```

---

## 3. Key Concepts

### 3.1 Worktree Creation

When spawning a teammate, create a worktree directory:

```python
worktree = WORKDIR / ".worktrees" / agent_name
worktree.mkdir(parents=True, exist_ok=True)
```

Optionally copy project files into the worktree so the agent starts with
something to work on.

### 3.2 Path Resolution per Agent

Each agent's `safe_path()` should resolve relative to ITS worktree, not the
main WORKDIR. The teammate loop needs to know its own worktree path.

### 3.3 Shared vs Isolated Resources

**Shared (in WORKDIR):**
- `.tasks/` -- task board (all agents need to see it)
- `.team/` -- team config and mailboxes
- `.transcripts/` -- compression transcripts
- `skills/` -- skill definitions

**Isolated (per worktree):**
- Source code files (each agent works on its own copy)
- Build artifacts, temp files

### 3.4 The Capstone: s_full.py

This file combines all mechanisms into one. It's structured in sections:

```
s_full.py:
  Section: base_tools (s02)         -> bash, read, write, edit
  Section: todos (s03)              -> TodoManager
  Section: subagent (s04)           -> run_subagent()
  Section: skills (s05)             -> SkillLoader
  Section: compression (s06)        -> micro_compact, auto_compact
  Section: file_tasks (s07)         -> TaskManager
  Section: background (s08)         -> BackgroundManager
  Section: messaging (s09)          -> MessageBus
  Section: shutdown + plan (s10)    -> protocol handlers
  Section: team (s09/s11)           -> TeammateManager with autonomy
  Section: global_instances         -> create all managers
  Section: system_prompt            -> combined system prompt
  Section: tool_dispatch (s02)      -> 24+ tools in one dispatch map
  Section: agent_loop               -> main loop with all integrations
  Section: repl                     -> REPL with /compact /tasks /team /inbox
```

---

## 4. Skeleton Code

### 4.1 Worktree Setup

```python
WORKTREES_DIR = WORKDIR / ".worktrees"

def create_worktree(agent_name: str) -> Path:
    """Create an isolated worktree for an agent."""
    worktree = WORKTREES_DIR / agent_name
    worktree.mkdir(parents=True, exist_ok=True)
    # TODO: Optionally copy project files into worktree
    # Hint: shutil.copytree or specific file copies
    return worktree
```

### 4.2 Per-Agent Path Resolution

In the teammate loop, track the worktree:

```python
def _teammate_loop(self, name: str, role: str, prompt: str):
    worktree = create_worktree(name)

    # Override safe_path for this agent
    def agent_safe_path(p: str) -> Path:
        path = (worktree / p).resolve()
        if not path.is_relative_to(worktree):
            raise ValueError(f"Path escapes workspace: {p}")
        return path

    # Pass worktree to tool execution
    # ...
```

### 4.3 Capstone: Global Instances

```python
# Global instances (all managers in one place)
TODO = TodoManager()
SKILLS = SkillLoader(SKILLS_DIR)
TASK_MGR = TaskManager()
BG = BackgroundManager()
BUS = MessageBus()
TEAM = TeammateManager(BUS, TASK_MGR)
```

### 4.4 Capstone: Combined Dispatch Map

```python
TOOL_HANDLERS = {
    # s02: base tools
    "bash": ...,
    "read_file": ...,
    "write_file": ...,
    "edit_file": ...,

    # s03: todos
    "TodoWrite": ...,

    # s04: subagent
    "task": ...,

    # s05: skills
    "load_skill": ...,

    # s06: compression
    "compress": ...,

    # s08: background
    "background_run": ...,
    "check_background": ...,

    # s07: file tasks
    "task_create": ...,
    "task_get": ...,
    "task_update": ...,
    "task_list": ...,

    # s09: team
    "spawn_teammate": ...,
    "list_teammates": ...,
    "send_message": ...,
    "read_inbox": ...,
    "broadcast": ...,

    # s10: protocols
    "shutdown_request": ...,
    "plan_approval": ...,

    # s11: autonomy
    "idle": ...,
    "claim_task": ...,
}
```

### 4.5 Capstone: Combined Agent Loop

The main loop now integrates s06, s08, s09, s10, and s03:

```python
def agent_loop(messages: list):
    rounds_without_todo = 0
    while True:
        # s06: micro_compact (every turn)
        micro_compact(messages)

        # s06: auto_compact (when threshold exceeded)
        if estimate_tokens(messages) > TOKEN_THRESHOLD:
            messages[:] = auto_compact(messages)

        # s08: drain background notifications
        notifs = BG.drain()
        if notifs:
            # TODO: Format and inject into messages

        # s09: check lead inbox
        inbox = BUS.read_inbox("lead")
        if inbox:
            # TODO: Inject into messages

        # LLM call
        response = client.messages.create(...)

        # Tool execution + s03 nag + s06 manual compact
        # TODO: Combine all the logic from previous sessions
```

### 4.6 Capstone: REPL Commands

```python
if __name__ == "__main__":
    history = []
    while True:
        query = input("s_full >> ")

        if query == "/compact":
            # TODO: manual compact
        elif query == "/tasks":
            # TODO: print task list
        elif query == "/team":
            # TODO: print team status
        elif query == "/inbox":
            # TODO: print lead inbox
        else:
            # Normal agent loop
```

---

## 5. Thought Exercises

1. **Should the lead agent also get a worktree?**
   Or should it work directly in WORKDIR? What are the tradeoffs?

2. **What if an agent needs to see another agent's output?**
   How would agents share completed work in a worktree setup?

3. **When should worktrees be cleaned up?**
   After shutdown? After task completion? Never?

4. **How would you test the full system end-to-end?**
   What's the simplest multi-agent scenario you can run?

---

## 6. Implementation Checklist

### Worktree Isolation
- [ ] `create_worktree()` creates `.worktrees/{name}/`
- [ ] Per-agent `safe_path()` resolves relative to worktree
- [ ] Teammate tools use worktree path, not global WORKDIR

### Capstone Integration
- [ ] All managers instantiated as globals
- [ ] Combined system prompt mentioning all tools
- [ ] 24+ tools in dispatch map
- [ ] Agent loop integrates: compression, background drain, inbox check, nag
- [ ] REPL with /compact, /tasks, /team, /inbox
- [ ] End-to-end test: create tasks, spawn team, watch autonomous work

---

## 7. Key Insight

> "The capstone isn't new code -- it's composition."

Every mechanism you built in s01-s11 works independently. The capstone just wires them
together. If any one mechanism is broken, the capstone won't work. If they're all clean,
composition is straightforward.

This is the reward for building incrementally. Each session was small. Together, they
form a production-quality agent system.

---

## 8. The Full Journey

```
s01: while True loop          -> 5 lines of core logic
s02: dispatch map             -> tools without changing the loop
s03: TodoManager              -> state as a tool
s04: subagents                -> fresh context for subtasks
s05: SkillLoader              -> on-demand knowledge
s06: 3-layer compression      -> infinite sessions
s07: TaskManager              -> persistent file-based tasks
s08: BackgroundManager        -> daemon threads + Queue
s09: MessageBus + Team        -> JSONL mailboxes, daemon agent loops
s10: Protocols                -> request_id correlation handshakes
s11: Autonomous claiming      -> idle agents find their own work
s12: Worktree + Capstone      -> isolation + put it all together
```

**You built all of this. From a while loop to a multi-agent system.**

---

*Implement `s12_worktree.py` and `s_full.py`. Paste your code and say "Review my s12 code."*
