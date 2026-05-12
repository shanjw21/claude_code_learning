# S11: Autonomous Agents -- "Idle agents claim tasks themselves"

---

## 1. What Problem Does This Solve?

In s09/s10, the lead assigns all work. But the lead is a bottleneck -- it has to
track who's idle, decide what to assign, and monitor progress.

**What if idle agents just... find their own work?**

When a teammate finishes its task and goes idle, it:
1. Checks its inbox for new messages
2. Scans the task board (s07 TaskManager) for unclaimed tasks
3. Claims the first available task
4. Goes back to work

**Decentralized work distribution. No dispatcher needed.**

---

## 2. Mental Model

```
Teammate Lifecycle with Autonomy:

+----------+     +----------+     +----------+     +----------+
| WORKING  | --> |   IDLE   | --> | scanning | --> | WORKING  |
| (50 rnd) |     | phase    |     | tasks    |     | (claimed |
|          |     |          |     |          |     |  task)   |
+----------+     +----------+     +----------+     +----------+
     |                |                |                |
     |                |                | no tasks       |
     |                |                v                |
     |                |          +----------+           |
     |                |          | SHUTDOWN |           |
     |                |          | (timeout)|           |
     |                |          +----------+           |
     |                |                                 |
     |                <--- new inbox message ------------+
     |                                                  |
     +<--- resume work on new message ------------------+
```

### The Idle Phase

```
Idle teammate polls every POLL_INTERVAL seconds:
  1. Check inbox -> if message, resume work
  2. Check task board -> if unclaimed task, claim it, resume work
  3. If neither after IDLE_TIMEOUT -> shutdown
```

---

## 3. Key Concepts

### 3.1 Two-Phase Teammate Loop

The teammate loop now has TWO phases:

```
WORK PHASE (up to 50 rounds):
  - Normal agent loop: check inbox, call LLM, execute tools
  - If model calls "idle" tool -> transition to IDLE phase
  - If model calls "claim_task" -> claim and continue

IDLE PHASE (polls for IDLE_TIMEOUT seconds):
  - Sleep POLL_INTERVAL seconds
  - Check inbox for new messages -> if found, resume WORK
  - Scan task board for unclaimed tasks -> if found, claim and resume WORK
  - After timeout with no work -> SHUTDOWN
```

### 3.2 New Teammate Tools

- `idle`: Model signals "I have nothing more to do right now"
- `claim_task`: Model (or idle scanner) claims a task by ID

### 3.3 Task Claiming Logic

When scanning for tasks, the idle agent looks for:
```python
# Pseudocode for unclaimed task detection
for task in all_tasks:
    if (task["status"] == "pending"
        and task.get("owner") is None
        and not task.get("blockedBy")):
        # This task is claimable!
        task_manager.claim(task["id"], agent_name)
```

### 3.4 Context Re-Injection

After the idle phase, the agent might have been asleep for a while. When it resumes,
inject identity back into messages (in case context was compressed):

```python
if len(messages) <= 3:
    messages.insert(0, {"role": "user", "content":
        f"You are '{name}', role: {role}, team: {team_name}."})
    messages.insert(1, {"role": "assistant", "content":
        f"I am {name}. Continuing."})
```

---

## 4. Skeleton Code

### 4.1 Modified Teammate Loop

```python
def _teammate_loop(self, name: str, role: str, prompt: str):
    sys_prompt = (f"You are '{name}', role: {role}, at {WORKDIR}. "
                  f"Use idle when done. You may auto-claim tasks.")
    messages = [{"role": "user", "content": prompt}]
    tools = self._teammate_tools()  # now includes idle + claim_task

    # ===== WORK PHASE =====
    while True:
        for _ in range(50):
            # TODO: Read inbox
            # TODO: Check for shutdown_request in inbox
            # TODO: Call LLM
            # TODO: Execute tools
            # TODO: If model called "idle", break out of work phase
            pass

        # ===== IDLE PHASE =====
        self._set_status(name, "idle")
        resume = False

        # TODO: Poll for IDLE_TIMEOUT / POLL_INTERVAL iterations
        for _ in range(IDLE_TIMEOUT // POLL_INTERVAL):
            time.sleep(POLL_INTERVAL)

            # Check inbox
            inbox = BUS.read_inbox(name)
            if inbox:
                # TODO: Check for shutdown_request
                # TODO: If regular message, append to messages, set resume=True
                break

            # Check for unclaimed tasks
            unclaimed = []
            for f in TASKS_DIR.glob("task_*.json"):
                t = json.loads(f.read_text())
                # TODO: What conditions make a task "unclaimed"?
                if t.get("status") == "___" and not t.get("___") and not t.get("___"):
                    unclaimed.append(t)

            if unclaimed:
                task = unclaimed[0]
                # TODO: Claim the task
                self.task_mgr.claim(task["id"], name)
                # TODO: Inject task into messages
                messages.append({"role": "user", "content":
                    f"Task #{task['id']}: {task['subject']}"})
                messages.append({"role": "assistant", "content":
                    f"Claimed task #{task['id']}. Working on it."})
                resume = True
                break

        if not resume:
            # No work found -> shutdown
            self._set_status(name, "shutdown")
            return

        # Resume work phase
        self._set_status(name, "working")
```

### 4.2 Teammate Tool Execution Updates

In `_exec()`, add handling for the new tools:

```python
if tool_name == "idle":
    return "Entering idle phase."

if tool_name == "claim_task":
    return self.task_mgr.claim(args["task_id"], sender)
```

### 4.3 Teammate Tools (add to `_teammate_tools()`)

```python
# idle tool
{
    "name": "idle",
    "description": "Signal that you have no more work to do.",
    "input_schema": {"type": "object", "properties": {}}
}

# claim_task tool
{
    "name": "claim_task",
    "description": "Claim a task from the task board by ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "integer"}
        },
        "required": ["task_id"]
    }
}
```

### 4.4 TaskManager.claim() (add to s07 TaskManager)

```python
def claim(self, tid: int, owner: str) -> str:
    """Claim a task for an owner."""
    task = self._load(tid)
    task["owner"] = owner
    task["status"] = "in_progress"
    self._save(task)
    return f"Claimed task #{tid} for {owner}"
```

### 4.5 Lead-Side Tools

Add `idle` and `claim_task` to the lead's tool set too (lead can also claim tasks):

```python
TOOL_HANDLERS = {
    # ... existing ...
    "idle":       lambda **kw: "Lead does not idle.",
    "claim_task": lambda **kw: TASK_MGR.claim(kw["task_id"], "lead"),
}
```

---

## 5. Thought Exercises

1. **What if two idle agents try to claim the same task simultaneously?**
   Is there a race condition? How could you make claiming atomic?

2. **Why check `blockedBy` when scanning for tasks?**
   What happens if an agent claims a task that's blocked?

3. **Why inject identity after idle phase?**
   What could happen if context was compressed during idle?

4. **Why not have the lead assign tasks instead?**
   What are the pros/cons of centralized vs decentralized task assignment?

---

## 6. Implementation Checklist

- [ ] `TaskManager.claim()` method added to s07 TaskManager
- [ ] `idle` and `claim_task` tools in teammate tool set
- [ ] Work phase / idle phase separation in `_teammate_loop()`
- [ ] Inbox polling during idle phase
- [ ] Task board scanning during idle phase
- [ ] Auto-claim when unclaimed task found
- [ ] IDLE_TIMEOUT and POLL_INTERVAL configuration
- [ ] Context re-injection after idle
- [ ] Shutdown when no work found after timeout
- [ ] Status transitions: working -> idle -> working / shutdown
- [ ] Lead-side `idle` and `claim_task` tools
- [ ] Test: create 3 tasks, spawn 2 teammates, watch them auto-claim

---

## 7. Key Insight

> "Idle agents find their own work. No dispatcher needed."

This is the transition from a single-agent system to a multi-agent system.
The lead doesn't micromanage -- it creates tasks and lets agents self-organize.

This pattern (autonomous task claiming) is how real multi-agent systems scale:
the work queue is the coordination mechanism, not a central dispatcher.

---

*Implement `s11_autonomous.py`. Paste your code and say "Review my s11 code."*
