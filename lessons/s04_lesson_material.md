# S04: Subagents -- "Fresh Context for Subtasks"

---

## 1. What Problem Does This Solve?

Your main agent loop (from s03) accumulates context -- `messages[]` grows with every tool call, every assistant response, every user input. If the agent tries to do everything in one loop, the context window fills up and the agent loses focus.

**Subagents solve this:** Spawn a temporary worker with a **clean `messages[]` array**, let it focus on one task, return a summary, and **die**.

```
Subagent (s04): spawn → execute with fresh context → return summary → destroyed
Teammate (s09):  spawn → work → idle → work → ... → shutdown  (persistent)

These are DIFFERENT patterns. Subagents are disposable.
```

### Why Does Context Pollution Matter?

Imagine your main agent has 50k tokens of history: todo updates, session commands, file edits. Now you ask it: *"Find all Python files with TODO comments."*

If the LLM tries to answer in the main loop:
- It has to wade through 50k tokens of irrelevant history
- Its response might be influenced by stale context ("should I update the todo?")
- Every API call costs more because the input is longer

**The subagent pattern:** Give it a **fresh start** with only the prompt. No history. No distraction.

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

**Key insight:** The subagent gets **ZERO context** from the parent. It only gets the prompt you send it. The parent sees only the final summary, never the intermediate steps.

### Data Flow Trace

```
User: "Find all Python files with TODO comments"
  → Main LLM receives this in its 50k-token messages[]
  → Main LLM decides: "this is a focused lookup task → use 'task' tool"
    → run_subagent(prompt="Find all .py files with TODO comments", agent_type="Explore")
      → sub_messages = [{"role": "user", "content": "Find all .py files with TODO comments"}]
        ← FRESH! Zero parent history!
      → Loop up to 30 rounds:
          → LLM call (input is tiny -- just the prompt)
          → LLM uses bash: find . -name "*.py" -exec grep -n "TODO" {} +
          → tool_result: "./s03_my_todolist.py:194: # TODO: What state does this hold?"
          → LLM summarizes: "Found 3 files with TODOs: s03_my_todolist.py (line 194)..."
          → stop_reason = "end_turn" (no more tool_use) → break
      → Extract final text → return to parent
    → Parent receives: "Found 3 files with TODOs: ..." (as tool_result)
  → Parent says to user: "I found 3 Python files with TODO comments: ..."
```

**Notice what the parent NEVER sees:**
- The subagent's `find` command
- The grep output
- The subagent's reasoning

Only the final summary. That keeps the parent's context clean.

---

## 3. Key Concepts

### 3.1 Context Isolation

The subagent starts with:
```python
sub_messages = [{"role": "user", "content": prompt}]
```

No parent history. No accumulated tool results. Nothing.

**Think about it:** What goes wrong if you pass the parent's full history?
1. The subagent gets confused by stale context
2. Every API call is expensive (50k+ tokens input)
3. The subagent might try to continue the parent's conversation instead of doing its task

### 3.2 Round Limits

Subagents run for a **fixed number of rounds** (e.g., 30). This prevents:
- Runaway API costs
- Infinite loops (LLM keeps calling tools forever)
- Task drift (subagent goes off-topic)

**Think about it:** What happens at round 31? The loop exits, and whatever the LLM last said becomes the result. If it never produced text (only tool calls), the result is empty.

### 3.3 Result Extraction

When the subagent finishes, you extract its **final text response** and return it as the `tool_result` to the parent. The parent sees the summary, not the subagent's full conversation.

```python
# resp is the last API response
text_blocks = [b.text for b in resp.content if b.type == "text"]
return "\n".join(text_blocks)
```

### 3.4 Agent Types: Explore vs General-Purpose

The `agent_type` parameter controls what tools the subagent has:

| Type | Tools | Use Case |
|------|-------|----------|
| `"Explore"` | bash + read_file | Research, find files, grep for patterns |
| `"general-purpose"` | bash + read + write + edit | Create files, make changes, build things |

**Why restrict tools?** An Explore-only subagent **cannot modify anything**. It eliminates the risk of a research task accidentally changing files. Think of it as a safety boundary.

---

## 4. Architecture Diagram

```
                    Main agent_loop()
                         |
                    User asks a question
                         |
                    LLM decides to delegate
                         |
                    LLM calls "task" tool
                         |
                         v
              +--------------------+
              | run_subagent()     |
              |                    |
              | sub_tools = [...]  |  ← depends on agent_type
              | sub_handlers = {}  |  ← dispatch table
              |                    |
              | sub_messages = [   |  ← FRESH, empty
              |   {"role":"user",  |
              |    "content":prompt}|
              |                    |
              | for N rounds:      |
              |   LLM call         |
              |   tool dispatch    |
              |   append results   |
              |                    |
              | extract final text |
              +--------+-----------+
                       |
                       v
              Return summary as tool_result
              Parent continues with subagent's answer in its messages[]
```

---

## 5. What You Need to Implement

There are **3 TODO sections** in `s04_subagents.py`. Here's what each one requires:

### TODO 1: The `task` Tool Definition (in TOOLS list)

Add the tool schema that tells the LLM when and how to spawn subagents:

```python
{
    "name": "task",
    "description": "Spawn a subagent for focused work. Use when you need to do a self-contained task that doesn't require the full conversation context.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The task description for the subagent."},
            "agent_type": {
                "type": "string",
                "enum": ["Explore", "general-purpose"],
                "description": "Explore = read-only (bash + read_file). general-purpose = full access (bash + read + write + edit)."
            }
        },
        "required": ["prompt"]
    }
}
```

**Key decisions you need to make:**
- What should the `enum` values for `agent_type` be? (Hint: look at section 3.4)
- Which fields are required? Does the user need to specify `agent_type` every time?

### TODO 2: `run_subagent()` -- The Core Function

This is the heart of s04. You need to fill in:

1. **`sub_tools`**: Define the tool schemas the subagent can use
   - Explore mode: only `bash` + `read_file`
   - General-purpose: `bash` + `read_file` + `write_file` + `edit_file`
   - Hint: You can copy these from the `TOOLS` list above

2. **`sub_handlers`**: Map tool names to handler functions
   - `"bash": tool_bash`
   - `"read_file": tool_read_file`
   - Add write/edit for general-purpose

3. **`sub_messages`**: Start with just the prompt
   ```python
   sub_messages = [{"role": "user", "content": prompt}]
   ```

4. **Round limit check**: After appending the assistant response, check if the LLM is asking for more tools:
   ```python
   if resp.stop_reason != "tool_use":
       break
   ```

5. **Result extraction**: Join all text blocks from the final response:
   ```python
   text_blocks = [b.text for b in resp.content if b.type == "text"]
   return "\n".join(text_blocks)
   ```

### TODO 3: Register the `task` Handler

Add to `TOOL_DICT`:
```python
"task": lambda **kw: run_subagent(kw["prompt"], kw.get("agent_type", "Explore")),
```

This wires the LLM's `task` tool call to your `run_subagent()` function.

---

## 6. Thought Exercises

1. **Why not share the parent's messages[] with the subagent?** What specific problems could occur if you pass the parent's full history?

2. **Why limit to 30 rounds?** What happens if a subagent runs 200 rounds? How does this affect API costs?

3. **Why would "Explore" mode not have write_file?** What risk does a read-only subagent eliminate?

4. **What happens if the subagent hits an API error?** Should the parent crash too, or receive an error message? How is this handled in the skeleton code?

5. **Design question:** If you wanted a subagent to return structured data (not just text), how would you change `run_subagent()`?

---

## 7. Implementation Checklist

- [ ] `task` tool definition added to `TOOLS`
- [ ] `task` handler registered in `TOOL_DICT`
- [ ] `run_subagent()` function with fresh `messages[]`
- [ ] Subagent tool definitions (bash + read_file for Explore)
- [ ] Subagent tool handlers (reuse existing handlers)
- [ ] Round limit (max 30 iterations) with `stop_reason` check
- [ ] Result extraction (join all text blocks from final response)
- [ ] Error handling (try/except around subagent loop)
- [ ] Test: delegate "list all .py files" to a subagent
- [ ] Test: try both Explore and general-purpose modes

---

## 8. Debugging Guide

| Symptom | Check This |
|---------|-----------|
| Subagent runs forever | Is your round limit working? Is `stop_reason != "tool_use"` checked? |
| Parent sees empty result | Is text extraction looking at the right response object (`resp`)? |
| Subagent can't write files | Did you include `write_file` in `sub_tools` for general-purpose mode? |
| API error crashes parent | Is the subagent loop wrapped in `try/except`? |
| LLM never uses the `task` tool | Is the tool description clear enough? Try: "Find X by delegating to a subagent" |
| Subagent sees stale context | Make sure `sub_messages` starts with ONLY `[{"role": "user", "content": prompt}]` |

---

## 9. Key Insight

> **"Subagents are disposable workers with clean context."**

This pattern is the foundation for:
- **s08** (background tasks): subagents that run without blocking
- **s09** (teammates): persistent agents that live beyond one task

Subagents are **ephemeral** -- they live, work, and die. Teammates are **persistent** -- they live, work, idle, and work again.

Understanding this distinction now will make s08 and s09 much easier.

---

## 10. How s04 Extends s03

| Component | s03 | s04 |
|-----------|-----|-----|
| Tools | bash, read, write, edit, todo | + **task** |
| Context | Session-persistent messages[] | **+ Fresh sub_messages[] per subagent** |
| Loop | Single agent_loop() | **+ run_subagent() nested loop** |
| Storage | SessionStore (JSONL) | Same (subagent results saved to parent session) |
| TodoManager | ✅ | Same (unchanged) |

The only new behavior: when the LLM calls `task`, the main loop delegates to a subagent instead of executing a tool directly.

---

*Implement the 3 TODO sections in `codes/s04_subagents.py`. Paste your code and say "Review my s04 code."*
