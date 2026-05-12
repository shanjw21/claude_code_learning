# S03 Review Guide -- TodoWrite

---

## 1. The "Why" -- Core Concept

| Question | Answer |
|----------|--------|
| What problem does TodoManager solve? | Agent forgets where it is in multi-step tasks |
| What pattern is this? | **State as a Tool** -- the agent reads/writes its own state by calling a tool |
| Where does this pattern repeat? | s07 (Tasks), s09 (Teams) |

---

## 2. Your Bugs -- What They Taught You

| Bug | Root Confusion | Lesson |
|-----|---------------|--------|
| `self.items` vs `items` parameter | Mixing "old state" with "new input" | `items` = what LLM sent (unvalidated). `self.items` = what you stored (validated). |
| `item.status` vs `item["status"]` | Object vs dict | JSON from LLM becomes Python **dicts**. Always use `["key"]`. |
| `return` vs `raise ValueError` | How LLM sees the result | `return` = LLM thinks success. `raise` = error that must be caught and converted to string. |
| `line.join("/n [] #")` | Misunderstanding `str.join()` | `join` joins an iterable with a separator. For building strings, use `+=`. |
| `line["id"]` instead of `item["id"]` | Confusing accumulator with loop variable | `item` = current dict. `line` = string being built. They are different types. |
| `TodoManager.update` in TOOL_DICT | Unbound method | Instance methods need an **instance**. Use a wrapper function or lambda. |
| Dual `messages.append` | New code + old code coexisting | When refactoring, **remove old code** that the new code replaces. |
| Extra `{}` in `results.append` | Syntax error | One dict = one pair of `{}`. `{{}}` = a set. |

---

## 3. Data Flow Checklist

Trace this every time you build a new tool:

```
[ ] Where does the data come from? (LLM -> JSON -> Python dicts)
[ ] What parameter receives it? (items, not self.items)
[ ] What shape is it? (dict? list? string?)
[ ] Do I validate it? (what can go wrong?)
[ ] Where do I store it? (self.items = validated_items)
[ ] What do I return? (string for the LLM to read)
```

---

## 4. Key Design Decisions to Remember

**Why full-list replacement, not delta updates?**
> Delta = "update item #3 to completed". What if item #3 was deleted? What if IDs shifted? Full replacement is simpler -- no merge conflicts.

**Why only 1 `in_progress`?**
> Forces the agent to focus. Without this, the agent marks 5 things "in progress" and finishes none.

**Why `type: "text"` for the nag, not `"tool_result"`?**
> `"tool_result"` requires a `tool_use_id`. The nag isn't from any tool -- it's injected by the harness. Wrong type = API rejection.

**Why `results.insert(0, ...)` not `append`?**
> The nag is the important message. Insert at position 0 so the LLM reads it first.

---

## 5. Testing Checklist

Run your agent and try these scenarios:

```
[ ] Give it a 3-step task. Does it call todo() to plan?
[ ] Does it mark items in_progress one at a time?
[ ] Does it mark items completed when done?
[ ] Send invalid status (e.g., "almost_done"). Does it get a clear error?
[ ] Send 2 items as in_progress. Does it get rejected?
[ ] Send 21 items. Does it get rejected?
[ ] Give it a task and watch -- after 3 rounds without todo, does the nag appear?
[ ] After the nag, does the agent update its todos?
[ ] Type /sessions, /new, /delete -- do they work?
[ ] Quit and restart -- does session persistence reload?
```

---

## 6. Self-Assessment Questions

Before moving to s04, answer these without looking at code:

1. What's the difference between `TodoManager.update()` receiving `items` vs reading `self.items`?
2. Why does `todo_tool()` wrap the call in `try/except ValueError`?
3. Where does `rounds_since_todo = 0` live -- inside or outside the inner loop? Why?
4. If you added a new tool called `search`, what 3 places in the code would you touch?

---

When you can answer all 4 confidently, you're ready for **s04: Subagents**.
