# S08: Background Tasks -- "Non-blocking async execution"

---

## 1. What Problem Does This Solve?

Some tasks take a long time (npm install, running test suites, building projects).
If the agent waits for each one, it's blocked from doing anything else.

**Background tasks run in daemon threads** while the main agent continues working.
Results come back through a notification queue.

---

## 2. Mental Model

```
Main Agent (single thread)          Background Thread
+-------------------------+         +------------------+
| "Run the test suite"    | spawn   | subprocess.run(  |
|                         | ------> |   "npm test"     |
| continue working...     |         | )                |
| "Edit config file"      |         | ...running...    |
| "Read README"           |         | ...running...    |
|                         | notify  | done!            |
| receives notification   | <------ | result in queue  |
+-------------------------+         +------------------+
```

---

## 3. Key Concepts

### 3.1 Daemon Threads

```python
thread = threading.Thread(target=worker_func, args=(...), daemon=True)
thread.start()
```

`daemon=True` means the thread dies when the main program exits. No orphan processes.

### 3.2 Queue for Notifications

```python
from queue import Queue

notifications = Queue()

# Background thread puts result:
notifications.put({"task_id": tid, "status": "completed", "result": "..."})

# Main thread drains queue:
while not notifications.empty():
    notif = notifications.get_nowait()
```

`Queue` is thread-safe. No locks needed.

### 3.3 Drain Pattern

Each time the main loop runs, it **drains** the notification queue. Any completed
background tasks are injected into the conversation as context for the model.

### 3.4 Task Tracking

A dictionary tracks all background tasks: `{task_id: {status, command, result}}`.
The `check` method lets the model ask about specific tasks.

---

## 4. Skeleton Code

### 4.1 BackgroundManager Class

```python
class BackgroundManager:
    def __init__(self):
        self.tasks = {}           # {task_id: {status, command, result}}
        self.notifications = Queue()  # thread-safe notification queue

    def run(self, command: str, timeout: int = 120) -> str:
        """Start a command in a background thread."""
        # TODO: Generate unique task_id
        # TODO: Create task entry with status="running"
        # TODO: Start daemon thread that calls self._exec()
        # TODO: Return "Background task {tid} started"
        pass

    def _exec(self, tid: str, command: str, timeout: int):
        """Worker function -- runs in background thread."""
        try:
            r = subprocess.run(
                command, shell=True, cwd=WORKDIR,
                capture_output=True, text=True, timeout=timeout
            )
            output = (r.stdout + r.stderr).strip()[:50000]
            self.tasks[tid].update({
                "status": "completed",
                "result": output or "(no output)"
            })
        except Exception as e:
            self.tasks[tid].update({
                "status": "error",
                "result": str(e)
            })

        # TODO: Put notification in queue
        self.notifications.put({
            "task_id": tid,
            "status": self.tasks[tid]["status"],
            "result": self.tasks[tid]["result"][:500]
        })

    def check(self, tid: str = None) -> str:
        """Check status of a specific task or all tasks."""
        if tid:
            t = self.tasks.get(tid)
            # TODO: Return formatted status
        # TODO: If no tid, return summary of ALL background tasks

    def drain(self) -> list:
        """Drain all pending notifications from the queue."""
        notifs = []
        while not self.notifications.empty():
            notifs.append(self.notifications.get_nowait())
        return notifs
```

### 4.2 Tool Definitions

```python
# background_run
{
    "name": "background_run",
    "description": "Run a shell command in the background. Non-blocking.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer"}
        },
        "required": ["___"]
    }
}

# check_background
# TODO: define -- optional task_id parameter
```

### 4.3 Integration in the Loop

```python
def agent_loop(messages: list):
    while True:
        # TODO: Drain background notifications BEFORE each LLM call
        notifs = BG.drain()
        if notifs:
            # TODO: Format notifications as text
            # TODO: Append as user message so the model sees them
            pass

        response = client.messages.create(...)
        # ... rest of loop ...
```

**Why drain BEFORE the LLM call?** So the model sees completed tasks and can act on them
in its next decision.

---

## 5. Thought Exercises

1. **Why `Queue` instead of a regular list for notifications?**
   What happens if the background thread and main thread write/read simultaneously?

2. **What if a background task never finishes?**
   Should there be a timeout at the thread level too?

3. **Why only put `result[:500]` in the notification?**
   The full result is in `self.tasks`. Why not send everything?

4. **Can you run multiple background tasks simultaneously?**
   What are the limits?

---

## 6. Implementation Checklist

- [ ] `BackgroundManager.__init__()` with tasks dict and Queue
- [ ] `run()` spawns daemon thread, returns task_id
- [ ] `_exec()` runs subprocess, updates status, puts notification
- [ ] `check()` returns single task or all tasks
- [ ] `drain()` empties notification queue
- [ ] `background_run` and `check_background` tool definitions
- [ ] Drain notifications in the main loop before each LLM call
- [ ] Test: start a background task, do other work, check the result

---

## 7. Key Insight

> "Daemon threads + Queue = async for free."

No event loop. No async/await. No framework. Just `threading.Thread(daemon=True)` and
`queue.Queue`. The simplest concurrency that works.

This pattern extends directly to s09 where entire agent loops run in daemon threads.

---

*Implement `s08_background.py`. Paste your code and say "Review my s08 code."*
