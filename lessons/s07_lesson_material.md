# S07: Tasks -- "File-based task graph with dependencies"

---

## 1. What Problem Does This Solve?

TodoManager (s03) is in-memory. It dies when the process exits. It can't be shared
between agents. It has no concept of dependencies.

**TaskManager persists tasks to disk as JSON files**, with dependency tracking via
`blockedBy` relationships. Tasks survive restarts and can be shared across agents.

---

## 2. Mental Model

```
s03 TodoManager (in-memory):          s07 TaskManager (file-based):
+---------------------------+         +-- .tasks/ ---------------+
| [>] #2: Write tests      |         | task_1.json              |
| (1/3 completed)           |         | task_2.json              |
+---------------------------+         | task_3.json              |
Dies on exit.                         +--------------------------+
Single agent only.                    Persists across restarts.
                                      Multiple agents can read/write.

Each task file:
{
  "id": 1,
  "subject": "Create project structure",
  "description": "Set up dirs and config",
  "status": "completed",
  "owner": null,
  "blockedBy": []
}

Dependency example:
  task_3 has "blockedBy": [1, 2]
  -> task_3 can't start until tasks 1 and 2 are done
```

---

## 3. Key Concepts

### 3.1 File-Based Persistence

Each task is a separate JSON file: `.tasks/task_{id}.json`. This means:
- Atomic reads/writes (no database needed)
- Easy debugging (just `cat .tasks/task_1.json`)
- Survives process restarts
- Multiple processes can read tasks

### 3.2 Dependency Tracking (`blockedBy`)

A task can declare it's blocked by other tasks:
```json
{"id": 3, "blockedBy": [1, 2], "status": "pending"}
```

When task 1 is completed, it should be removed from all `blockedBy` arrays.
This "unblocks" dependent tasks automatically.

### 3.3 CRUD Operations

Four operations, four tools:
- `task_create(subject, description)` -> returns task JSON
- `task_get(task_id)` -> returns single task
- `task_update(task_id, status, add_blocked_by, remove_blocked_by)` -> returns updated task
- `task_list()` -> returns all tasks with status indicators

### 3.4 Auto-increment IDs

IDs are integers, auto-incremented by scanning existing files:
```python
def _next_id(self) -> int:
    ids = [int(f.stem.split("_")[1]) for f in TASKS_DIR.glob("task_*.json")]
    return max(ids, default=0) + 1
```

---

## 4. Skeleton Code

### 4.1 TaskManager Class

```python
TASKS_DIR = WORKDIR / ".tasks"

class TaskManager:
    def __init__(self):
        # TODO: Create .tasks/ directory if it doesn't exist

    def _next_id(self) -> int:
        """Get the next available task ID by scanning existing files."""
        # TODO: glob for task_*.json, extract IDs, return max + 1

    def _load(self, tid: int) -> dict:
        """Load a task from disk."""
        # TODO: Read .tasks/task_{tid}.json
        # TODO: Raise ValueError if not found

    def _save(self, task: dict):
        """Save a task to disk."""
        # TODO: Write .tasks/task_{task['id']}.json

    def create(self, subject: str, description: str = "") -> str:
        """Create a new task."""
        task = {
            "id": self._next_id(),
            "subject": subject,
            "description": description,
            "status": "pending",
            "owner": None,
            "blockedBy": []
        }
        # TODO: Save and return JSON string

    def get(self, tid: int) -> str:
        """Get a task by ID."""
        # TODO: Load and return as JSON string

    def update(self, tid: int, status: str = None,
               add_blocked_by: list = None,
               remove_blocked_by: list = None) -> str:
        """Update task status and/or dependencies."""
        task = self._load(tid)
        if status:
            task["status"] = status

        # TODO: When status is "completed", remove this task's ID
        #       from all other tasks' blockedBy arrays
        #       (this unblocks dependent tasks!)
        if status == "completed":
            # TODO: Scan all task files, remove tid from their blockedBy
            pass

        # TODO: When status is "deleted", delete the file
        if status == "deleted":
            # TODO: Delete the file and return
            pass

        # TODO: Handle add_blocked_by and remove_blocked_by
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        if remove_blocked_by:
            task["blockedBy"] = [x for x in task["blockedBy"]
                                 if x not in remove_blocked_by]

        # TODO: Save and return

    def list_all(self) -> str:
        """List all tasks with status markers."""
        # TODO: Load all tasks, render with [ ], [>], [x] markers
        # TODO: Show owner and blockedBy info
        # Example output:
        # [x] #1: Create project structure
        # [>] #2: Write tests @alice (blocked by: [3])
        # [ ] #3: Add documentation
```

### 4.2 Tool Definitions (4 tools)

```python
# task_create
{
    "name": "task_create",
    "description": "___",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "description": {"type": "string"}
        },
        "required": ["___"]
    }
}

# task_get
# TODO: define -- needs task_id (integer)

# task_update
# TODO: define -- needs task_id, optional: status, add_blocked_by, remove_blocked_by

# task_list
# TODO: define -- no parameters needed
```

### 4.3 Dispatch Registration

```python
TOOL_HANDLERS = {
    # ... existing tools ...
    "task_create": lambda **kw: TASK_MGR.create(kw["subject"], kw.get("description", "")),
    "task_get":    lambda **kw: TASK_MGR.get(kw["task_id"]),
    "task_update": lambda **kw: TASK_MGR.update(kw["task_id"], kw.get("status"),
                                                  kw.get("add_blocked_by"),
                                                  kw.get("remove_blocked_by")),
    "task_list":   lambda **kw: TASK_MGR.list_all(),
}

TASK_MGR = TaskManager()
```

---

## 5. Thought Exercises

1. **Why JSON files instead of SQLite?**
   What are the tradeoffs? When would a database be better?

2. **What happens if two agents update the same task simultaneously?**
   Is there a race condition? How would you fix it?

3. **Why auto-remove from `blockedBy` on completion?**
   What if you DON'T auto-remove? What does the agent see?

4. **Why is `blockedBy` an array, not a single value?**
   Can you think of a task that depends on multiple others?

---

## 6. Implementation Checklist

- [ ] `TaskManager.__init__()` creates `.tasks/` directory
- [ ] `_next_id()` scans existing files for auto-increment
- [ ] `_load()` / `_save()` for single-task file I/O
- [ ] `create()` with subject, description, status="pending", empty blockedBy
- [ ] `get()` returns single task JSON
- [ ] `update()` handles status changes + blockedBy modifications
- [ ] Auto-unblock: completing a task removes it from others' blockedBy
- [ ] Delete support: status="deleted" removes the file
- [ ] `list_all()` renders all tasks with markers
- [ ] 4 tool definitions in `TOOLS` array
- [ ] 4 handlers in `TOOL_HANDLERS`
- [ ] REPL command: `/tasks` prints task list
- [ ] Test: create 3 tasks where task 3 is blocked by 1 and 2

---

## 7. Key Insight

> "File-based persistence: no database, no server, just JSON on disk."

This is the "harness philosophy" again. Tasks don't need a complex system. A directory
of JSON files is sufficient. Simple, debuggable, and shareable between agents.

The dependency tracking pattern (`blockedBy`) will be used again in s11 when
agents autonomously claim tasks -- they check `blockedBy` before claiming.

---

*Implement `s07_tasks.py`. Paste your code and say "Review my s07 code."*
