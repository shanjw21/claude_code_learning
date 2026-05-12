# S10: Team Protocols -- "Structured handshakes between models"

---

## 1. What Problem Does This Solve?

In s09, teammates communicate with simple messages. But some interactions need structure:

- **Shutdown:** "Please stop" needs a request/response handshake. The teammate might
  reject it (it's in the middle of important work).
- **Plan Approval:** A teammate should submit its plan before doing major work.
  The lead reviews and approves/rejects.

**Both use the same pattern: request with a UUID, response correlated by that UUID.**

---

## 2. Mental Model

```
Shutdown Protocol:
  Lead                                    Teammate
  +------------------+                   +------------------+
  | shutdown_request | ---(req_id)-----> | receives request |
  |                  |                   | decides: y/n?    |
  +------------------+                   +------------------+
  +------------------+                   +-------v----------+
  | checks status    | <---(req_id)----- | shutdown_response|
  | approved/rejected|                   | {approve: true}  |
  +------------------+                   +------------------+
          |
          v
  if approved: teammate status -> "shutdown", thread exits

Plan Approval Protocol:
  Teammate                              Lead
  +------------------+                  +------------------+
  | plan_approval    | ---(req_id)----> | reviews plan     |
  | {plan: "..."}    |                  | approves?        |
  +------------------+                  +------------------+
  +------------------+                  +-------v----------+
  | receives result  | <---(req_id)---- | plan_approval    |
  | approved/rejected|                  | {approve: true}  |
  +------------------+                  +------------------+
```

---

## 3. Key Concepts

### 3.1 Request ID Correlation

Every request gets a unique ID (`uuid4()[:8]`). The response carries the same ID.
This lets you track which response matches which request.

```python
import uuid
req_id = str(uuid.uuid4())[:8]
```

### 3.2 Request Trackers

Two dictionaries track in-flight requests:

```python
shutdown_requests = {}  # {req_id: {"target": name, "status": "pending"}}
plan_requests = {}      # {req_id: {"from": name, "plan": text, "status": "pending"}}
```

### 3.3 Thread Safety

Multiple threads access these trackers. Use `threading.Lock()`:

```python
_tracker_lock = threading.Lock()

with _tracker_lock:
    shutdown_requests[req_id] = {"target": name, "status": "pending"}
```

### 3.4 Two-Sided Tools

Shutdown has tools on BOTH sides:
- **Lead:** `shutdown_request` (initiate) + `shutdown_response` (check status)
- **Teammate:** `shutdown_response` (respond with approve/reject)

Plan approval has tools on BOTH sides:
- **Teammate:** `plan_approval` (submit plan)
- **Lead:** `plan_approval` (approve/reject submitted plan)

Note the asymmetry: both sides have a tool called `plan_approval` but they do
different things depending on who calls it.

---

## 4. Skeleton Code

### 4.1 Request Trackers

```python
import threading

shutdown_requests = {}
plan_requests = {}
_tracker_lock = threading.Lock()
```

### 4.2 Lead-Side: Shutdown Request

```python
def handle_shutdown_request(teammate: str) -> str:
    """Lead initiates a shutdown request to a teammate."""
    req_id = str(uuid.uuid4())[:8]

    # TODO: Track the request
    with _tracker_lock:
        shutdown_requests[req_id] = {"target": teammate, "status": "pending"}

    # TODO: Send the request via MessageBus
    BUS.send("lead", teammate, "Please shut down gracefully.",
             "shutdown_request", {"request_id": req_id})

    return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"
```

### 4.3 Lead-Side: Plan Review

```python
def handle_plan_review(request_id: str, approve: bool, feedback: str = "") -> str:
    """Lead approves or rejects a teammate's plan."""
    with _tracker_lock:
        req = plan_requests.get(request_id)
        if not req:
            return f"Error: Unknown plan request_id '{request_id}'"

    # TODO: Update status
    with _tracker_lock:
        req["status"] = "approved" if approve else "rejected"

    # TODO: Send response to teammate
    BUS.send("lead", req["from"], feedback,
             "plan_approval_response",
             {"request_id": request_id, "approve": approve, "feedback": feedback})

    return f"Plan {req['status']} for '{req['from']}'"
```

### 4.4 Teammate-Side: Shutdown Response

In the teammate's `_exec()` method, add:

```python
if tool_name == "shutdown_response":
    req_id = args["request_id"]
    approve = args["approve"]

    # TODO: Update the tracker
    with _tracker_lock:
        if req_id in shutdown_requests:
            shutdown_requests[req_id]["status"] = "approved" if approve else "rejected"

    # TODO: Send response back to lead via MessageBus
    BUS.send(sender, "lead", args.get("reason", ""),
             "shutdown_response",
             {"request_id": req_id, "approve": approve})

    return f"Shutdown {'approved' if approve else 'rejected'}"
```

### 4.5 Teammate-Side: Plan Submission

```python
if tool_name == "plan_approval":
    plan_text = args.get("plan", "")
    req_id = str(uuid.uuid4())[:8]

    # TODO: Track the request
    with _tracker_lock:
        plan_requests[req_id] = {"from": sender, "plan": plan_text, "status": "pending"}

    # TODO: Send to lead for review
    BUS.send(sender, "lead", plan_text,
             "plan_approval_response",
             {"request_id": req_id, "plan": plan_text})

    return f"Plan submitted (request_id={req_id}). Waiting for lead approval."
```

### 4.6 Handling Shutdown in Teammate Loop

In `_teammate_loop`, detect when shutdown is approved:

```python
should_exit = False

for _ in range(50):
    # ... inbox check, LLM call, tool execution ...

    for block in response.content:
        if block.type == "tool_use":
            output = self._exec(name, block.name, block.input)
            # TODO: If shutdown_response approved, set should_exit = True
            if block.name == "shutdown_response" and block.input.get("approve"):
                should_exit = True

    if should_exit:
        break

# TODO: Set status to "shutdown" if should_exit, else "idle"
```

### 4.7 Tool Definitions (3 new tools)

```python
# Lead-side tools:

# shutdown_request
{
    "name": "shutdown_request",
    "description": "Request a teammate to shut down gracefully.",
    "input_schema": {
        "type": "object",
        "properties": {
            "teammate": {"type": "string"}
        },
        "required": ["___"]
    }
}

# shutdown_response (lead-side: check status)
# TODO: define -- takes request_id

# plan_approval (lead-side: approve/reject)
# TODO: define -- takes request_id, approve (boolean), optional feedback
```

---

## 5. Thought Exercises

1. **Why use `threading.Lock()` instead of just trusting single-threaded access?**
   Which threads access these trackers?

2. **What if a teammate never responds to a shutdown request?**
   Should there be a timeout? What happens to the tracker?

3. **Why `uuid4()[:8]` instead of a sequential integer?**
   What's the risk of predictable IDs in a multi-agent system?

4. **The teammate checks `shutdown_request` in its inbox AND as a tool.**
   Why handle it in both places? (Hint: what if the teammate is idle?)

---

## 6. Implementation Checklist

- [ ] Request trackers with `threading.Lock`
- [ ] `handle_shutdown_request()` on lead side
- [ ] `handle_plan_review()` on lead side
- [ ] `shutdown_response` handler in teammate `_exec()`
- [ ] `plan_approval` handler in teammate `_exec()`
- [ ] `should_exit` flag in teammate loop
- [ ] Teammate tools include shutdown_response + plan_approval
- [ ] Lead tools include shutdown_request + plan_approval
- [ ] Status transitions: working -> shutdown on approve
- [ ] Test: spawn teammate, send shutdown request, verify graceful exit

---

## 7. Key Insight

> "Same request_id pattern, two domains."

Shutdown and plan approval look different but are the same pattern:
1. Generate a unique request ID
2. Send request via MessageBus with that ID
3. Track status in a dictionary
4. Response comes back with the same ID
5. Update tracker

Learn this pattern once, apply it everywhere. This is how real distributed systems work.

---

*Implement `s10_team_protocols.py`. Paste your code and say "Review my s10 code."*
