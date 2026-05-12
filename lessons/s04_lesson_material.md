# S04: Subagents -- "Fresh context for subtasks"

---

## 1. What Problem Does This Solve?

Your main agent accumulates context -- messages grow with every tool call. If it tries to
do everything in one loop, the context window fills up and the agent loses focus.

**Subagents solve this:** spawn a temporary worker with a clean `messages[]` array,
let it focus on one task, return a summary, and die.

```
Subagent (s04): spawn -> execute with fresh context -> return summary -> destroyed
Teammate (s09):  spawn -> work -> idle -> work -> ... -> shutdown  (persistent)

These are DIFFERENT patterns. Subagents are disposable.
```

---

## 2. Mental Model

```
Main Agent                        Subagent
+------------------+              +------------------+
| messages[] (50k  |   spawn      | messages[] (0)   |
| tokens of        | -----------> | + user prompt    |
| history)         |              |                  |
|                  |   summary    | works for N      |
|                  | <----------- | rounds, returns  |
| continues...     |              | result, destroyed|
+------------------+              +------------------+
```

Key: the subagent gets ZERO context from the parent. It only gets the prompt you send it.

---

## 3. Key Concepts

### 3.1 Context Isolation

The subagent starts with `messages = [{"role": "user", "content": prompt}]`.
No parent history leaks in. This is critical -- the parent might have 50k tokens
of irrelevant context that would confuse the subagent.

### 3.2 Round Limits

Subagents run for a fixed number of rounds (e.g., 10-30). This prevents:
- Runaway API costs
- Infinite loops
- The subagent drifting off-task

### 3.3 Result Extraction

When the subagent finishes, you need to extract its final text response and return
it as the `tool_result` to the parent agent. The parent sees the summary, not the
subagent's full conversation.

### 3.4 Agent Types (Bonus)

The reference implementation has an `agent_type` parameter:
- `"Explore"`: read-only subagent (only bash + read_file)
- `"general-purpose"`: full subagent (bash + read + write + edit)

**Why would you restrict tools?** Think about what an exploration-only agent should be able to do.

---

## 4. Architecture Diagram

```
                    Main agent_loop()
                         |
                    LLM calls "task" tool
                         |
                         v
              +--------------------+
              | run_subagent()    |
              |                   |
              | sub_messages = [] |  <-- FRESH, empty
              | + user prompt     |
              |                   |
              | for N rounds:    |
              |   LLM call       |
              |   tool dispatch  |
              |   append results |
              |                   |
              | extract final text|
              +--------+---------+
                       |
                       v
              Return summary as tool_result to parent
              Parent continues with subagent's answer
```

---

## 5. Skeleton Code -- Fill In The Blanks

### 5.1 The `run_subagent` Function

```python
def run_subagent(prompt: str, agent_type: str = "Explore") -> str:
    """
    Spawn a temporary agent with fresh context.
    Returns a text summary of what it did.
    """
    # TODO: Define subagent tools
    # Hint: if agent_type == "Explore", only bash + read_file
    #       otherwise, add write_file + edit_file too
    sub_tools = [
        # TODO: Add tool definitions (same JSON Schema format as s02)
    ]

    # TODO: Define subagent tool handlers
    sub_handlers = {
        # "bash": ...,
        # "read_file": ...,
        # "write_file": ... (only if not Explore),
        # "edit_file": ... (only if not Explore),
    }

    # TODO: Create FRESH messages array (this is the core idea!)
    sub_messages = [
        # TODO: What goes here? Just the prompt.
    ]

    resp = None
    # TODO: Run the loop for max N rounds (e.g., 30)
    for _ in range(___):
        resp = client.messages.create(
            model=MODEL, messages=sub_messages,
            tools=sub_tools, max_tokens=8000
        )
        sub_messages.append({"role": "assistant", "content": resp.content})

        # TODO: Check stop_reason -- if not "tool_use", break

        # TODO: Execute tools using sub_handlers dispatch
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                # TODO: dispatch to handler, collect tool_result
                pass
        sub_messages.append({"role": "user", "content": results})

    # TODO: Extract final text from the last response
    # Hint: look for blocks with .text attribute in resp.content
    if resp:
        return ___  # TODO: join all text blocks
    return "(subagent failed)"
```

### 5.2 Tool Definition for "task"

```python
{
    "name": "task",
    "description": "___DESCRIBE_WHEN_TO_USE_THIS___",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "agent_type": {
                "type": "string",
                # TODO: What values should this accept?
                "enum": ["___", "___"]
            }
        },
        "required": ["___"]
    }
}
```

### 5.3 Dispatch Registration

```python
TOOL_HANDLERS = {
    # ... existing tools from s02/s03 ...
    "task": lambda **kw: run_subagent(kw["prompt"], kw.get("agent_type", "___")),
}
```

---

## 6. Thought Exercises

1. **Why not share the parent's messages[] with the subagent?**
   What could go wrong if you pass the parent's full history?

2. **Why limit to 30 rounds?**
   What happens if a subagent runs 200 rounds?

3. **Why would "Explore" mode not have write_file?**
   What risk does a read-only subagent eliminate?

4. **What happens if the subagent fails (exception)?**
   Should the parent crash too, or receive an error message?

---

## 7. Implementation Checklist

- [ ] `run_subagent()` function with fresh `messages[]`
- [ ] Subagent tool definitions (at minimum bash + read_file)
- [ ] Subagent tool handlers (reuse existing `run_bash`, `run_read`, etc.)
- [ ] Round limit (max 30 iterations)
- [ ] Result extraction (join text blocks from final response)
- [ ] `task` tool definition added to `TOOLS`
- [ ] `task` handler added to `TOOL_HANDLERS`
- [ ] Optional: `agent_type` parameter with Explore vs general-purpose
- [ ] Test: delegate "list all .py files" to a subagent

---

## 8. Debugging Guide

| Symptom | Check This |
|---------|-----------|
| Subagent runs forever | Is your round limit working? Is `stop_reason` checked? |
| Parent sees empty result | Is text extraction looking at the right response object? |
| Subagent can't write files | Did you include write_file in the sub_tools? |
| API error in subagent crashes parent | Wrap subagent in try/except, return error as string |

---

## 9. Key Insight

> "Subagents are disposable workers with clean context."

This pattern is the foundation for s08 (background tasks) and s09 (teammates).
Subagents are ephemeral -- they live, work, and die. Teammates are persistent --
they live, work, idle, and work again.

---

*Implement `s04_subagents.py`. Paste your code and say "Review my s04 code."*
