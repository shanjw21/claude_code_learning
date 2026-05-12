# S05: Skills -- "On-demand capability loading"

---

## 1. What Problem Does This Solve?

Your agent has a fixed set of tools. But sometimes it needs specialized knowledge --
how to review a PR, how to write a commit message, how to debug a specific framework.

**Skills are markdown files the agent loads on demand.** When loaded, the skill content
is injected into the conversation as context the model can follow.

---

## 2. Mental Model

```
skills/
  SKILL.md          <-- agent loads this when needed
  +------------------+
  | ---              |
  | name: commit     |  <-- YAML frontmatter (metadata)
  | description: ... |
  | ---              |
  | # How to commit  |  <-- Markdown body (instructions)
  | 1. Check diff    |
  | 2. Write message |
  +------------------+

When model calls load_skill("commit"):
  -> SkillLoader reads SKILL.md
  -> Parses YAML frontmatter
  -> Returns body text as tool_result
  -> Model now has the instructions in context
```

---

## 3. Key Concepts

### 3.1 YAML Frontmatter

A SKILL.md file has two parts separated by `---`:

```markdown
---
name: commit-review
description: Review code changes
trigger: review, PR
---
# Commit Review Skill
1. Read the diff
2. Check for common mistakes
3. Write a summary
```

The YAML block is metadata (for filtering, discovery). The body is the actual
instruction the model follows.

### 3.2 Regex Parsing

You need to split the file at the `---` boundaries. The pattern is:

```
^---\n(.*?)\n---\n(.*)    (with re.DOTALL so . matches newlines)
```

Group 1 = YAML text, Group 2 = body text.

### 3.3 Skill Discovery

The `SkillLoader` scans the skills directory at startup and builds an index.
When the model asks to load a skill, it's a simple dictionary lookup.

The system prompt should include available skill names so the model knows what exists.

---

## 4. Skeleton Code

### 4.1 SkillLoader Class

```python
import re

class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills = {}
        # TODO: Scan skills_dir for SKILL.md files
        if skills_dir.exists():
            for f in sorted(skills_dir.rglob("SKILL.md")):
                text = f.read_text()
                # TODO: Use regex to split YAML frontmatter from body
                # Pattern: ^---\n(.*?)\n---\n(.*)
                # Hint: use re.match() with re.DOTALL
                match = re.match(r"___", text, re.DOTALL)
                meta, body = {}, text
                if match:
                    # TODO: Parse YAML lines into meta dict
                    # Each line like "name: commit-review" -> {"name": "commit-review"}
                    for line in match.group(1).strip().splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip()] = v.strip()
                    body = match.group(2).strip()

                name = meta.get("name", f.parent.name)
                self.skills[name] = {"meta": meta, "body": body}

    def descriptions(self) -> str:
        """Return a summary of available skills for the system prompt."""
        if not self.skills:
            return "(no skills)"
        # TODO: Build a string like " - commit: Review code changes"
        # Hint: use meta.get('description', '-') for each skill
        pass

    def load(self, name: str) -> str:
        """Load a skill by name. Return body text or error."""
        s = self.skills.get(name)
        if not s:
            available = ", ".join(self.skills.keys())
            return f"Error: Unknown skill '{name}'. Available: {available}"
        # TODO: Return the body text
```

### 4.2 Tool Definition

```python
{
    "name": "load_skill",
    "description": "___",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"}
        },
        "required": ["name"]
    }
}
```

### 4.3 Dispatch and System Prompt

```python
SKILLS = SkillLoader(SKILLS_DIR)  # SKILLS_DIR = WORKDIR / "skills"

TOOL_HANDLERS = {
    # ... existing tools ...
    "load_skill": lambda **kw: SKILLS.load(kw["name"]),
}

# The system prompt should tell the model what skills are available
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Skills available: {SKILLS.descriptions()}
Use load_skill to get specialized instructions."""
```

---

## 5. Thought Exercises

1. **Why scan at startup instead of on demand?**
   What's the tradeoff?

2. **What if a skill file has malformed YAML?**
   Should the whole thing fail, or fall back gracefully?

3. **Should skills be able to define NEW tools?**
   Or are they just instruction text? What are the limits?

---

## 6. Implementation Checklist

- [ ] `SkillLoader.__init__()` scans for SKILL.md files
- [ ] YAML frontmatter parsing with regex
- [ ] `SkillLoader.descriptions()` returns summary for system prompt
- [ ] `SkillLoader.load()` returns body text or error
- [ ] Create a `skills/` directory with at least one sample SKILL.md
- [ ] `load_skill` tool added to `TOOLS` and `TOOL_HANDLERS`
- [ ] System prompt includes skill descriptions
- [ ] Test: ask agent to load a skill and follow its instructions

---

## 7. Key Insight

> "Skills are just markdown the model reads on demand."

No special infrastructure. Just file reading + regex parsing + returning text
as a tool result. The model treats skill content the same as any other context.

This is the "harness philosophy" in miniature: you don't build intelligence,
you build the environment that lets the model be intelligent.

---

*Implement `s05_skills.py`. Paste your code and say "Review my s05 code."*
