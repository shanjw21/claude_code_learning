# S03: TodoWrite -- "The agent tracks its own progress"

---

## 1. What Problem Does This Solve?

By s02, your agent has tools (bash, read, write, edit). But give it a multi-step task
and watch it drift -- it forgets what step it's on, repeats work, has no sense of progress.

**TodoWrite gives the agent structured state it writes to and reads from.**

You gain **visibility** into the agent's internal plan.

---

## 2. Mental Model

```
Before s03:
  User -> LLM -> Tool -> Result -> LLM -> Tool -> Result -> ...
  (linear, no memory of progress)

After s03:
  User -> LLM -> TodoWrite([plan]) -> Tool -> TodoWrite([update]) -> Tool -> ...
  (agent maintains a visible task list)

  TodoManager State (in-memory):
  +-----------------------------------+
  | [ ] #1: Create project structure  |
  | [>] #2: Write main.py            |  <-- currently working
  | [ ] #3: Add tests                |
  |                                   |
  | (0/3 completed)                   |
  +-----------------------------------+
```

---

## 3. Key Concepts

### 3.1 The Tool IS the State

The `TodoManager` is not special infrastructure. It's just another handler in the
dispatch map, like `run_bash` or `run_read`. The model calls it, passes data in,
gets data back.

**Your task:** Add ONE entry to `TOOL_HANDLERS` and ONE entry to `TOOLS`.

### 3.2 Validation Rules You Must Enforce

| Rule | Why |
|------|-----|
| Max 20 items | Prevents endless lists |
| Only 1 `in_progress` at a time | Forces focus |
| `text` field required | No empty tasks |
| Status must be `pending`, `in_progress`, or `completed` | No made-up statuses |
| `id` field required | Stable references across updates |

### 3.3 The Nag Reminder

If the agent forgets to update todos for 3 rounds, inject a text hint:
`"Update your todos."` into the results.

This is a **harness-level policy** -- not a tool, but logic in the loop itself.

---

## 4. Architecture Diagram

```
                agent_loop()
                    |
                    v
              +--------------------+
              | LLM API call       |
              +--------+-----------+
                       |
                       v
              +--------------------+
              | Check stop_reason  |
              +--------+-----------+
                       |
              tool_use?|--- no --> return
                       |
                       v
              +--------------------+
              | For each block:    |
              |   dispatch to      |
              |   TOOL_HANDLERS    |
              +--------+-----------+
                       |
                       v
              +--------------------+     <-- YOU BUILD THIS
              | Was "todo" called? |
              |   yes: reset count |
              |   no:  count++     |
              +--------+-----------+
                       |
                       v
              +--------------------+     <-- YOU BUILD THIS
              | count >= 3?        |
              |   yes: insert nag  |
              +--------+-----------+
                       |
                       v
              Append results as user message, loop back
```

---

## 5. Skeleton Code -- Fill In The Blanks

### 5.1 TodoManager Class

```python
class TodoManager:
    def __init__(self):
        # TODO: What state does this hold?

    def update(self, items: list) -> str:
        """
        Accept a FULL replacement list (not a delta).
        Validate every item. If valid, store and return rendered view.
        If invalid, raise ValueError with a clear message.
        """
        # TODO: Check max 20 items
        # TODO: Loop through items, validate each one:
        #   - text must be non-empty
        #   - status must be one of: "pending", "in_progress", "completed"
        #   - id must be present
        #   - count how many are "in_progress"
        # TODO: After loop: check only 1 in_progress
        # TODO: Store validated list
        # TODO: Return self.render()

    def render(self) -> str:
        """
        Return a human-readable string like:
        [ ] #1: Create project
        [>] #2: Write tests
        [x] #3: Setup git

        (1/3 completed)
        """
        # TODO: Handle empty case -> return "No todos."
        # TODO: Build lines with markers: "[ ]" for pending, "[>]" for in_progress, "[x]" for completed
        # TODO: Add completion count at the bottom
```

**Design hint:** `update()` receives the FULL list every time, not a delta. Think about
why this is simpler than "update item #3 to completed".

### 5.2 Tool Definition for "todo"

```python
{
    "name": "todo",
    "description": "___WRITE_A_DESCRIPTION_THAT_HELPS_THE_MODEL_KNOW_WHEN_TO_USE_THIS___",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        # TODO: What fields does each todo item need?
                        # Hint: id, text, status (with enum!)
                    },
                    "required": ["___", "___", "___"]
                }
            }
        },
        "required": ["___"]
    }
}
```

**Hint:** Look at how the s02 tool definitions are structured. Same pattern, different fields.

### 5.3 Nag Reminder in the Loop

Your `agent_loop` from s02 needs three additions. Study the skeleton -- the `___` marks
what you need to fill in:

```python
# Before inner loop:                                                                                                       
  rounds_since_todo = ___                                                                                                                      
  while True:                                                                                                                
      response = client.messages.create(                                                                                     
          model=model_name,                                                                                                  
          max_tokens=4096,                                                                                                   
          messages=messages,                                                                                                 
          tools=TOOLS                                                                                                        
      )                                                                                                                      
      messages.append({"role": "assistant", "content": response.content})                                                    
      store.save_message(session_key, "assistant", response.content)                                                         
                                                                                                                             
      tool_use_blocks = [b for b in response.content if b.type == "tool_use"]                                                
      if tool_use_blocks:                                                                                                    
          results = []                                                                                                       
          todo_called = ___    # track this round                                                                            
                                                                                                                             
          for block in tool_use_blocks:                                                                                      
              print(f"\n[Tool: {block.name}]")                                                                               
              print(f"  Input: {block.input}\n")                                                                             
              tool_use_result = process_tool_call(tool_name=block.name, tool_input=block.input)                              
              print(f"  Result: {tool_use_result[:200]}")                                                                    
                                                                                                                             
              results.append({                                                                                               
                  "type": "tool_result",                                                                                     
                  "tool_use_id": block.id,                                                                                   
                  "content": tool_use_result                                                                                 
              })                                                                                                             
              store.save_message(session_key, "tool_result", tool_use_result, block.id)                                      
                                                                                                                             
              if ___:            # was the tool named "todo"?                                                                
                  todo_called = ___                                                                                          
                  rounds_since_todo = ___                                                                                    
                                                                                                                             
          # --- Nag logic ---                                                                                                
          if not todo_called:                                                                                                
              rounds_since_todo ___                                                                                          
          if rounds_since_todo >= 3:                                                                                         
              results.___(___, {           # insert at the beginning                                                         
                  "type": "___",           # "text", NOT "tool_result"                                                       
                  "text": "Update your todos."                                                                               
              })                                                                                                             
                                                                                                                             
          messages.append({"role": "user", "content": results})                                                              
          continue
      else:                                                                                                                  
          text = "\n".join(b.text for b in response.content if b.type == "text")                                             
          print(f"\nAgent > {text}\n")                                                                                       
          break 
```

**Why `results.insert(0, ...)` instead of `results.append(...)`?** Think about what
the model sees first when it reads the tool results.

### 5.4 System Prompt

```python
SYSTEM = f"""You are a coding agent at {WORKDIR}.
___ADD_AN_INSTRUCTION_ABOUT_THE_TODO_TOOL___
Prefer tools over prose."""
```

**Why does this matter?** Without mentioning the todo tool in the system prompt,
the model may never discover it exists.

---

## 6. Data Flow Trace (Read, Don't Implement)

User says: "Create a Python project with main.py and test_main.py"

```
Round 1:
  LLM calls: todo(items=[
    {id:"1", text:"Create main.py", status:"pending"},
    {id:"2", text:"Create test_main.py", status:"pending"},
  ])
  Result -> "[ ] #1: Create main.py\n[ ] #2: Create test_main.py\n(0/2 completed)"

Round 2:
  LLM calls: todo(items=[
    {id:"1", text:"Create main.py", status:"in_progress"},  <-- marked active
    {id:"2", text:"Create test_main.py", status:"pending"},
  ])
  Result -> "[>] #1: Create main.py\n[ ] #2: Create test_main.py\n(0/2 completed)"

Round 3:
  LLM calls: write_file(path="main.py", content="...")
  Result -> "Wrote 42 bytes"
  rounds_since_todo = 1  (no todo this round!)

Round 4:
  LLM calls: todo(items=[
    {id:"1", text:"Create main.py", status:"completed"},    <-- marked done
    {id:"2", text:"Create test_main.py", status:"in_progress"},
  ])
  rounds_since_todo = 0  (reset!)

... and so on until all completed.
```

**What if the model forgets todos for 3 rounds?**
```
Round N:   no todo -> count = 1
Round N+1: no todo -> count = 2
Round N+2: no todo -> count = 3 -> NAG INJECTED before tool results
```

---

## 7. What Changed from s02

### Same as s02:
- `agent_loop()` core structure (while True -> API -> check stop -> execute -> append)
- All 4 tools: bash, read_file, write_file, edit_file
- `safe_path()`, `run_bash()`, `run_read()`, `run_write()`, `run_edit()`
- The dispatch map pattern
- The REPL `__main__` block

### You add:
- [ ] `TodoManager` class
- [ ] `todo` tool in `TOOLS` array
- [ ] `todo` handler in `TOOL_HANDLERS`
- [ ] `rounds_since_todo` counter + nag injection in `agent_loop()`
- [ ] Updated system prompt
- [ ] try/except around tool execution (bonus: prevents one bad tool from crashing the loop)

---

## 8. Thought Exercises (Answer Before Coding)

1. **Why full-list replacement instead of delta updates?**
   What could go wrong if you allowed "update item #3 status to completed"?

2. **Why limit to 1 `in_progress`?**
   What happens if an agent marks 5 items as in_progress simultaneously?

3. **Why is the nag `type: "text"` and not `type: "tool_result"`?**
   What would break if you used the wrong type?

---

## 9. Implementation Checklist

- [ ] `TodoManager.__init__()` -- initialize state
- [ ] `TodoManager.update()` -- validate + store + return rendered string
- [ ] `TodoManager.render()` -- `[ ]`, `[>]`, `[x]` markers + completion count
- [ ] Validation: max 20 items
- [ ] Validation: only 1 `in_progress`
- [ ] Validation: text required, status must be valid
- [ ] `todo` tool definition added to `TOOLS`
- [ ] `todo` handler added to `TOOL_HANDLERS`
- [ ] `rounds_since_todo` counter in loop
- [ ] Nag injection when count >= 3
- [ ] System prompt mentions todo tool
- [ ] try/except around tool calls

---

## 10. Debugging Guide

| Symptom | Check This |
|---------|-----------|
| Model never calls `todo` | System prompt instruction + tool description |
| Model sends invalid status | Does your validation return a clear error as tool_result? |
| Nag never triggers | Is `rounds_since_todo` incremented in the right branch? |
| `render()` shows wrong state | Is `self.items = validated` before or after `render()`? |
| Model updates only 1 item | Does your system prompt tell it to send the FULL list? |

---

## 11. Extension Challenges (After Basic Implementation Works)

- Add a `/todos` REPL command that prints current state
- Persist todos to `.todos.json` (save on update, load on start)
- Add a 4th status: `blocked` with an optional `reason` field
- Make the nag smarter: include current state in the nag message

---

## 12. Key Insight

> "The agent can track its own progress -- and I can see it."

This pattern -- **state as a tool** -- repeats in s07 (TaskManager) and s09 (TeammateManager).
Master it here.

---

*When you're ready, implement `s03_todo_write.py`. Paste your code and say "Review my s03 code."*


## 13.知识点补充
### 1.subprocess.run() -> CompletedProgress
- 参数:
command:要执行的命令（字符串或列表）
shell=True: 是否通过shell执行
capture_output=True:捕获stdout和stderr
timeout:超过时间抛出TimeoutExpired异常
text=True:以文本模式输出，返回str而非bytes

- 返回值 CompletedProgress
result.returncode:返回码，0表示成功
result.stdout: 标准输出
result.stderr: 标准错误

### 2.ps.path.dirname(path)获取目录路径
- 如果path包含目录部分("a/b/c/file.txt")，返回目录路径"a/b/c"
- 如果path只是文件名(file.txt)，返回空字符串

os.mkdirs(dirname,exist_ok=True) 创建多级目录
- dirname:要创建的目录路径
- True:目录已存在，静默跳过，不抛异常
