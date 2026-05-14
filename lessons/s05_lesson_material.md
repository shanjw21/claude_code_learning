# S05: Skills -- "按需加载技能"

---

## 1. 要解决什么问题？

你的 Agent 已经有了固定的工具集（bash、read_file、write_file、todo、task）。但有时候它需要**特定领域的知识**：

- 怎么写一个符合项目规范的 commit message？
- 怎么做 code review？
- 怎么排查某个框架的 bug？

这些知识**不应该写死在系统 prompt 里**——那会浪费大量 token，而且大部分时间用不上。

**Skills 的解法：按需加载 markdown。** 当 Agent 需要某个技能时，调用 `load_skill` 工具读取对应的 `SKILL.md` 文件，内容作为上下文注入到对话中。

```
skills/
  commit/SKILL.md       ← commit message 规范
  code-review/SKILL.md  ← code review 流程
  debug/SKILL.md        ← 调试指南

Agent 调用 load_skill("commit") → 读取文件 → 返回内容给 LLM → LLM 按指示操作
```

---

## 2. 心智模型

### 文件结构

一个 `SKILL.md` 文件由两部分组成，用 `---` 分隔：

```markdown
---
name: commit
description: 生成符合项目规范的 commit message
trigger: commit, message, 提交
---
# Commit Message 规范

## 格式
<type>(<scope>): <subject>

## type 可选值
- feat: 新功能
- fix: 修复 bug
- refactor: 重构
- docs: 文档更新
- style: 格式调整
- test: 测试相关

## 示例
feat(todo): add batch delete functionality
fix(session): handle missing session key gracefully
```

- **YAML frontmatter**（`---` 之间的部分）：元数据，用于发现、过滤、触发词匹配
- **Body**（第二个 `---` 之后的部分）：实际指令，LLM 读取后遵循

### 数据流

```
启动时:
  SkillLoader.__init__(skills_dir/)
    → 递归扫描所有 SKILL.md
    → 解析 YAML frontmatter → 提取 name/description
    → 构建 skills = {"commit": {meta: {...}, body: "..."}, ...}

运行时:
  User: "帮我写个 commit message"
    → LLM 查看可用技能 → 调用 load_skill("commit")
      → SkillLoader.load("commit") 返回 body 文本
        → LLM 读到具体规范 → 按格式生成 commit message
```

---

## 3. 核心概念

### 3.1 启动时扫描 vs 按需读取

**启动时扫描：** 启动时扫描整个 `skills/` 目录，建立 `skills` 索引（只读 metadata）。

**按需读取 Body：** 真正的 body 内容在启动时就已经读入内存了（因为文件通常很小）。如果技能文件很大（几十 KB），可以改为只在 `load()` 时才读取文件内容。

**思考：** 为什么要在启动时扫描？不能等到 LLM 第一次调用 `load_skill` 时再扫描吗？

> 如果按需扫描，系统 prompt 里就无法列出可用技能，LLM 就不知道该调用什么。

### 3.2 YAML Frontmatter 解析

Python 标准库没有内置 YAML 解析器（`yaml` 需要 `pip install PyYAML`）。我们选择**手动解析**：

```python
# 每行都是 "key: value" 格式
for line in yaml_text.splitlines():
    if ":" in line:
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
```

这足够处理简单的键值对。如果 skill 需要数组或多行字符串，可以用 PyYAML，但对于 learn-claude-code 的目标来说，手动解析足够了。

### 3.3 系统 Prompt 中的技能发现

启动时，`SkillLoader.descriptions()` 生成一个简短的技能列表，放入系统 prompt：

```
Available skills:
- commit: 生成符合项目规范的 commit message
- code-review: 代码审查流程
Use load_skill to get detailed instructions.
```

这样 LLM 知道有哪些技能可用，但**不需要占用大量 token 来加载具体内容**。

---

## 4. 架构图

```
                    启动时
                       |
                       v
              +--------------------+
              | SkillLoader()      |
              |                    |
              | for SKILL.md:     |
              |   parse frontmatter|
              |   build index:    |
              |   {name: {meta,body}}|
              +--------+-----------+
                       |
                       v
              系统 Prompt: "Available skills: - commit: xxx"

                    运行时
                       |
                    LLM 调用 load_skill
                       |
                       v
              +--------------------+
              | SKILLS.load(name)  |
              |   → lookup by name |
              |   → return body    |
              +--------+-----------+
                       |
                       v
              Body text 作为 tool_result 返回给 LLM
              LLM 获得具体指令，继续执行
```

---

## 5. 实现指南（详细步骤 + 参考代码）

`s05_skills.py` 基于 s04 的代码，新增 3 个 TODO 区域。以下是每个 TODO 的详细实现指引。

### TODO 1: load_skill 工具定义

在 `TOOLS` 列表末尾添加新工具：

```python
{
    "name": "load_skill",
    "description": "Load a skill file to get specialized instructions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The skill name."}
        },
        "required": ["name"]
    }
}
```

### TODO 2: 注册 load_skill handler

在 `TOOL_DICT` 中添加一行：

```python
"load_skill": lambda **kw: SKILLS.load(kw["name"]),
```

### TODO 3: SkillLoader 类

#### 3.1 `__init__()` — 扫描 + 解析

```python
def __init__(self, skills_dir: Path):
    self.skills = {}
    if not skills_dir.exists():
        return

    for f in sorted(skills_dir.rglob("SKILL.md")):
        text = f.read_text()
        # 正则分隔 YAML frontmatter 和 body
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        meta, body = {}, text
        if match:
            for line in match.group(1).strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = match.group(2).strip()

        name = meta.get("name", f.parent.name)
        self.skills[name] = {"meta": meta, "body": body}
```

正则 `^---\n(.*?)\n---\n(.*)` 说明：
- `^---\n` — 文件开头的第一行 `---`
- `(.*?)` — 非贪婪匹配，捕获 YAML 部分（group 1）
- `\n---\n` — 分隔线
- `(.*)` — 剩余全部内容（group 2，body）
- `re.DOTALL` — 让 `.` 匹配换行符

#### 3.2 `descriptions()` — 返回技能摘要

```python
def descriptions(self) -> str:
    if not self.skills:
        return "(no skills available)"
    lines = []
    for name, skill in self.skills.items():
        desc = skill["meta"].get("description", "(no description)")
        lines.append(f" - {name}: {desc}")
    return "\n".join(lines)
```

#### 3.3 `load()` — 按名查找

```python
def load(self, name: str) -> str:
    skill = self.skills.get(name)
    if not skill:
        available = ", ".join(self.skills.keys())
        return f"Error: Unknown skill '{name}'. Available: {available}"
    return skill["body"]
```

### TODO 4: SYSTEM_PROMPT 追加技能列表

```python
SYSTEM_PROMPT = (
    "You are a coding agent. "
    "When doing research, ALWAYS use the 'task' tool. "
    f"Skills available: {SKILLS.descriptions()} "
    "Use load_skill(name) to get detailed instructions."
)
```

---

## 6. 思考题

1. **为什么启动时扫描而不是按需读取？** 权衡是什么？

2. **如果某个 SKILL.md 的 YAML 格式错误怎么办？** 应该让整个程序崩溃，还是跳过这个文件？

3. **技能应该能定义新的工具吗？** 还是只是纯文本指令？各自的限制是什么？

4. **如果技能文件很大（100KB），全部加载到上下文会怎样？** 有什么优化策略？

5. **设计题：** 你想给 Agent 加一个"自动发现触发技能"的能力（比如看到代码变更自动加载 code-review skill），怎么实现？

---

## 7. 实现清单

- [ ] `SkillLoader.__init__()` 扫描 SKILL.md 文件
- [ ] YAML frontmatter 正则解析
- [ ] `SkillLoader.descriptions()` 返回技能摘要
- [ ] `SkillLoader.load()` 返回 body 或错误
- [ ] 创建 `skills/` 目录，至少放一个示例 SKILL.md
- [ ] `load_skill` 工具添加到 `TOOLS` 和 `TOOL_DICT`
- [ ] 系统 prompt 包含技能列表
- [ ] 测试：让 Agent 加载一个技能并按指示操作

---

## 8. 调试指南

| 症状 | 检查 |
|------|------|
| Agent 说"没有可用技能" | 技能目录路径对吗？SKILL.md 文件名正确吗？ |
| 技能加载后 LLM 没反应 | body 内容是否为空？系统 prompt 里技能描述够清晰吗？ |
| YAML 解析出错 | 检查 `---` 分隔符是否正确（前后各一行空行） |
| 系统 prompt 里技能列表为空 | `descriptions()` 方法返回了什么？ |

---

## 9. 核心洞察

> **"Skills 就是 LLM 按需阅读的 markdown 文件。"**

没有特殊基础设施。就是：文件读取 + 正则解析 + 返回文本作为工具结果。LLM 把技能内容当成普通上下文来处理。

这就是 "harness 哲学" 的微观体现：你不构建智能，你构建让模型展现智能的环境。

---

*在 `codes/s05_skills.py` 中实现 TODO 部分。完成后粘贴代码并说 "Review my s05 code."*
