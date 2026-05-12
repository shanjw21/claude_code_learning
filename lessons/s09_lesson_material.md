# S09: Agent Teams -- "JSONL mailboxes for inter-agent communication"

---

## 1. What Problem Does This Solve?

Subagents (s04) are disposable -- spawn, work, return, die. They can't collaborate
over time. They can't message each other.

**Teammates are persistent agents** that run in daemon threads, communicate through
file-based JSONL inboxes, and have a lifecycle: working -> idle -> working -> ...

---

## 2. Mental Model

```
.team/
  config.json              inbox/
  +-------------------+    +-------------+
  | {                 |    | alice.jsonl |
  |   "team_name":    |    | bob.jsonl   |
  |     "default",    |    | lead.jsonl  |
  |   "members": [    |    +-------------+
  |     {"name":      |
  |      "alice",     |    send_message("alice", "fix the bug"):
  |      "role":      |    -> appends JSON line to alice.jsonl
  |      "coder",     |
  |      "status":    |    read_inbox("alice"):
  |      "idle"}      |    -> reads all lines, then CLEARS the file
  |   ]               |       (drain pattern, same as s08 queue)
  | }                 |
  +-------------------+

Thread: alice                   Thread: bob
+-------------------------+    +-------------------------+
| agent_loop in thread    |    | agent_loop in thread    |
| reads inbox each round  |    | reads inbox each round  |
| calls tools             |    | calls tools             |
| sends messages          |    | sends messages          |
| status -> idle when done|    | status -> idle when done|
+-------------------------+    +-------------------------+
```

---

## 3. Key Concepts

### 3.1 JSONL Mailboxes

Each agent has an inbox file (`alice.jsonl`). Messages are appended as JSON lines:

```jsonl
{"type":"message","from":"lead","content":"fix the login bug","timestamp":1712000000}
{"type":"broadcast","from":"lead","content":"standup time","timestamp":1712000060}
```

**Append-only writes, drain reads:**
- `send()`: opens file in append mode, writes one JSON line
- `read_inbox()`: reads all lines, then clears the file (drain)

### 3.2 MessageBus

A shared class that manages all mailboxes:

```python
class MessageBus:
    def send(sender, to, content, msg_type, extra)
    def read_inbox(name) -> list     # drain pattern
    def broadcast(sender, content, teammates)
```

### 3.3 TeammateManager

Manages persistent named agents:

```python
class TeammateManager:
    def spawn(name, role, prompt)    # starts daemon thread
    def list_all() -> str            # shows all teammates + status
    def member_names() -> list       # for broadcast
```

### 3.4 Teammate Lifecycle

```
spawn("alice", "coder", "Fix the login bug")
  -> config.json updated: alice status="working"
  -> daemon thread starts
  -> alice runs agent_loop for 50 rounds (work phase)
  -> alice done -> status="idle"
  -> idle phase: polls inbox, checks for messages
  -> receives message -> status="working", back to work phase
  -> no messages for a while -> status="shutdown" or stays idle
```

### 3.5 Message Types

```python
VALID_MSG_TYPES = {
    "message",
    "broadcast",
    "shutdown_request",      # s10
    "shutdown_response",     # s10
    "plan_approval_response" # s10
}
```

s09 implements `message` and `broadcast`. s10 adds the protocol types.

---

## 4. Skeleton Code

### 4.1 MessageBus

```python
class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        # TODO: Create inbox directory

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        # TODO: Validate msg_type against VALID_MSG_TYPES
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
        }
        if extra:
            msg.update(extra)
        # TODO: Append to {to}.jsonl
        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        """Read all messages, then CLEAR the file (drain)."""
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        # TODO: Read all JSON lines
        messages = []
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                messages.append(json.loads(line))
        # TODO: Clear the file (drain!)
        inbox_path.write_text("")
        return messages

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        # TODO: Send to every teammate except sender
        pass
```

### 4.2 TeammateManager

```python
class TeammateManager:
    def __init__(self, team_dir: Path):
        self.dir = team_dir
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.config = self._load_config()
        self.threads = {}

    def _load_config(self) -> dict:
        # TODO: Read config.json if exists, else return default
        pass

    def _save_config(self):
        # TODO: Write config.json
        pass

    def _find_member(self, name: str) -> dict:
        # TODO: Find member by name in config["members"]
        pass

    def spawn(self, name: str, role: str, prompt: str) -> str:
        """Spawn a teammate in a daemon thread."""
        member = self._find_member(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save_config()

        # TODO: Start daemon thread running self._teammate_loop()
        thread = threading.Thread(
            target=self._teammate_loop,
            args=(name, role, prompt),
            daemon=True,
        )
        self.threads[name] = thread
        thread.start()
        return f"Spawned '{name}' (role: {role})"

    def _teammate_loop(self, name: str, role: str, prompt: str):
        """The teammate's own agent loop -- runs in a thread."""
        sys_prompt = f"You are '{name}', role: {role}, at {WORKDIR}. Use send_message to communicate."
        messages = [{"role": "user", "content": prompt}]
        tools = self._teammate_tools()

        for _ in range(50):  # work phase: max 50 rounds
            # TODO: Read inbox at start of each round
            inbox = BUS.read_inbox(name)
            for msg in inbox:
                messages.append({"role": "user", "content": json.dumps(msg)})

            # TODO: Call LLM (same pattern as main loop)
            try:
                response = client.messages.create(
                    model=MODEL, system=sys_prompt,
                    messages=messages, tools=tools, max_tokens=8000
                )
            except Exception:
                break

            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break

            # TODO: Execute tool calls using self._exec()
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = self._exec(name, block.name, block.input)
                    results.append({...})
            messages.append({"role": "user", "content": results})

        # TODO: Set status to "idle" when done
        member = self._find_member(name)
        if member and member["status"] != "shutdown":
            member["status"] = "idle"
        self._save_config()

    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        """Execute a tool call from a teammate."""
        if tool_name == "bash":
            return run_bash(args["command"])
        if tool_name == "send_message":
            return BUS.send(sender, args["to"], args["content"])
        if tool_name == "read_inbox":
            return json.dumps(BUS.read_inbox(sender), indent=2)
        # TODO: Add read_file, write_file, edit_file
        return f"Unknown tool: {tool_name}"

    def _teammate_tools(self) -> list:
        """Tool definitions for teammates (subset of lead tools)."""
        return [
            # TODO: bash, read_file, write_file, edit_file,
            #       send_message, read_inbox
        ]
```

### 4.3 Lead Agent Tools

```python
TOOL_HANDLERS = {
    # ... existing tools ...
    "spawn_teammate": lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]),
    "list_teammates": lambda **kw: TEAM.list_all(),
    "send_message":   lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")),
    "read_inbox":     lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2),
    "broadcast":      lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()),
}
```

### 4.4 Inbox Check in Main Loop

```python
def agent_loop(messages: list):
    while True:
        # TODO: Check lead's inbox before each LLM call
        inbox = BUS.read_inbox("lead")
        if inbox:
            messages.append({
                "role": "user",
                "content": json.dumps(inbox, indent=2)
            })
            messages.append({
                "role": "assistant",
                "content": "Noted inbox messages."
            })

        response = client.messages.create(...)
        # ... rest of loop ...
```

---

## 5. Thought Exercises

1. **Why JSONL and not a database for messages?**
   What are the tradeoffs for inter-agent communication?

2. **Why drain the inbox on read?**
   What happens if you DON'T clear the file? Messages get re-read infinitely!

3. **Why does each teammate get its OWN tool set?**
   Should teammates be able to spawn other teammates? Why or why not?

4. **What happens if a teammate's thread crashes?**
   How would you detect and handle it?

---

## 6. Implementation Checklist

- [ ] `MessageBus` with send, read_inbox (drain), broadcast
- [ ] JSONL append-only writes, drain reads
- [ ] `TeammateManager` with config.json persistence
- [ ] `spawn()` creates daemon thread
- [ ] `_teammate_loop()` runs agent loop in thread
- [ ] `_exec()` handles teammate tool calls (including send_message)
- [ ] `_teammate_tools()` returns teammate-specific tool definitions
- [ ] Lead tools: spawn_teammate, list_teammates, send_message, read_inbox, broadcast
- [ ] Inbox check in main loop
- [ ] REPL commands: `/team`, `/inbox`
- [ ] Status updates in config.json at lifecycle transitions
- [ ] Test: spawn a teammate, send it a task, read its response

---

## 7. Key Insight

> "File-based mailboxes: the simplest inter-agent communication that works."

No message broker, no RPC, no network. Just files on disk. One agent writes,
the other reads and clears. It's the same philosophy as s07's task persistence:
use the filesystem as your database.

---

*Implement `s09_agent_teams.py`. Paste your code and say "Review my s09 code."*
