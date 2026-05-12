# S06: Context Compact -- "Strategic forgetting for infinite sessions"

---

## 1. What Problem Does This Solve?

Every tool call adds messages. After 50 rounds, your context is huge. The API has
token limits. The agent gets slow and expensive.

**Three-layer compression** keeps the agent working indefinitely:

```
Layer 1: micro_compact   (silent, every turn, free)
Layer 2: auto_compact    (LLM summarization, when threshold exceeded)
Layer 3: compact tool    (manual, model triggers it)
```

---

## 2. Mental Model

```
Messages growing over time:
  [user] [assistant] [user(3 tool_results)] [assistant] [user(3 tool_results)] ...
                                                                              ^
                                                                              |
                                                                    50k+ tokens!

After Layer 1 (micro_compact):
  [user] [assistant] [user(3 shortened)] [assistant] [user(3 shortened)] ...
   Old tool results replaced with: "[Previous: used bash]"

After Layer 2 (auto_compact):
  [user: "Compressed. Transcript saved. Summary: Created 3 files, fixed 1 bug..."]
  [assistant: "Understood. Continuing."]
   EVERYTHING replaced with 2 messages containing a summary.
```

---

## 3. Key Concepts

### 3.1 Micro Compact (Layer 1)

Runs every turn. Finds old `tool_result` entries in the messages and replaces their
content with a short placeholder like `"[Previous: used bash]"`.

Only the last N tool results are kept in full. Everything older gets truncated.

### 3.2 Auto Compact (Layer 2)

When estimated tokens exceed a threshold (e.g., 50000):
1. Save the FULL transcript to `.transcripts/` (don't lose data)
2. Ask the LLM to summarize the conversation
3. Replace ALL messages with: `[user: summary] + [assistant: "Understood"]`

### 3.3 Manual Compact (Layer 3)

The model itself can call a `compact` tool. This triggers the same logic as auto_compact
but is initiated by the model when it "feels" the context is getting unwieldy.

### 3.4 Token Estimation

A rough approximation: `len(str(messages)) // 4` (~4 chars per token).
Not exact, but good enough for threshold detection.

---

## 4. Skeleton Code

### 4.1 Token Estimation

```python
def estimate_tokens(messages: list) -> int:
    """Rough token count: ~4 chars per token."""
    # TODO: How do you estimate?
    # Hint: json.dumps(messages, default=str) gives you a string representation
    return ___
```

### 4.2 Micro Compact (Layer 1)

```python
KEEP_RECENT = 3  # keep last 3 tool results in full

def micro_compact(messages: list) -> list:
    """
    Replace old tool_result content with placeholders.
    Only keeps last KEEP_RECENT results in full.
    """
    # TODO: Collect all tool_result dicts from messages
    # Hint: iterate messages, find role=="user" with list content,
    #       find dicts with type=="tool_result"
    tool_results = []
    for msg in messages:
        if msg["role"] == "___" and isinstance(msg.get("content"), ___):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "___":
                    tool_results.append(part)

    if len(tool_results) <= KEEP_RECENT:
        return messages  # nothing to compact

    # TODO: For all but the last KEEP_RECENT results,
    #       replace long content (>100 chars) with a placeholder
    for result in tool_results[:-___]:
        if isinstance(result.get("content"), str) and len(result["content"]) > 100:
            result["content"] = "[Previous: used ___]"  # TODO: how to know which tool?

    return messages
```

**Hint for matching tool names:** You need to look at assistant messages for
`tool_use` blocks, build a `{tool_use_id: tool_name}` map, then use that to
label the placeholders.

### 4.3 Auto Compact (Layer 2)

```python
TRANSCRIPT_DIR = WORKDIR / ".transcripts"

def auto_compact(messages: list) -> list:
    """
    Save full transcript, ask LLM to summarize, replace all messages.
    """
    # Step 1: Save transcript to disk (data safety!)
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{___}.jsonl"  # TODO: unique name
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")

    # Step 2: Ask LLM to summarize
    conversation_text = json.dumps(messages, default=str)[:___]  # TODO: truncate to fit
    response = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content":
            "Summarize this conversation for continuity. Include:\n"
            "1) What was accomplished\n"
            "2) Current state\n"
            "3) Key decisions\n\n" + conversation_text
        }],
        max_tokens=2000,
    )
    summary = response.content[0].text

    # Step 3: Replace all messages with summary
    return [
        {"role": "user", "content":
            f"[Compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content":
            "Understood. I have the context from the summary. Continuing."},
    ]
```

### 4.4 Integration in the Loop

```python
def agent_loop(messages: list):
    while True:
        # Layer 1: micro_compact before each LLM call
        micro_compact(messages)

        # Layer 2: auto_compact if tokens exceed threshold
        if estimate_tokens(messages) > THRESHOLD:
            print("[auto_compact triggered]")
            messages[:] = auto_compact(messages)  # NOTE: [:] for in-place replacement

        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return

        results = []
        manual_compress = False
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "compact":
                    manual_compress = True
                    output = "Compressing..."
                else:
                    # ... normal tool dispatch ...
                    pass
                results.append(...)

        messages.append({"role": "user", "content": results})

        # Layer 3: manual compact
        if manual_compress:
            messages[:] = auto_compact(messages)
            return  # or continue -- think about which
```

---

## 5. Thought Exercises

1. **Why `messages[:] = auto_compact(messages)` instead of `messages = auto_compact(messages)`?**
   The caller holds a reference to the original list. Which approach modifies it in-place?

2. **Why save the transcript BEFORE compacting?**
   What happens if the LLM fails mid-summarization?

3. **What if the summary itself exceeds the threshold?**
   Could this loop forever?

4. **Why is micro_compact "free" but auto_compact costs an API call?**
   Think about the latency and token budget implications.

---

## 6. Implementation Checklist

- [ ] `estimate_tokens()` function
- [ ] `micro_compact()` replaces old tool results with placeholders
- [ ] Tool name tracking (map tool_use_id to tool_name)
- [ ] `auto_compact()` saves transcript + summarizes + replaces
- [ ] `compact` tool definition and handler
- [ ] Integration: micro_compact runs before each LLM call
- [ ] Integration: auto_compact triggers at token threshold
- [ ] Integration: manual compact when model calls `compact` tool
- [ ] `.transcripts/` directory creation
- [ ] Test: run a long task and observe compression happening

---

## 7. Key Insight

> "The agent can forget strategically and keep working forever."

Compression is what separates a demo from a production agent. Without it, every
agent session has a hard timeout. With it, agents can work on arbitrarily long tasks.

The 3-layer design means the common case (micro) is free, and expensive summarization
only happens when needed.

---

*Implement `s06_context_compact.py`. Paste your code and say "Review my s06 code."*
