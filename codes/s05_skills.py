#!/usr/bin/env python3
"""
s05: Skills -- "按需加载能力"

在 s04 基础上添加 Skills 系统。核心思路：
Agent 需要特定领域知识时，按需加载 skills/ 目录下的 SKILL.md 文件，
内容作为上下文注入到对话中。

Key insight: Skills 就是 LLM 按需阅读的 markdown 文件。
没有特殊基础设施，只有文件读取 + 正则解析 + 返回文本。
"""

import os
import re
import subprocess
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import time

# Load environment
load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

WORKDIR = Path(__file__).resolve().parent
client = anthropic.Anthropic(api_key=API_KEY, base_url=BASE_URL)

# ============================================================================
# TOOLS -- s04 tools + the new "load_skill" tool
# ============================================================================

TOOLS = [
    {
        "name": "bash",
        "description": "Execute a shell command and return the output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute."},
                "timeout": {"type": "integer", "description": "Maximum wait time in seconds."}
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Read and return the file's contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The path to the file to read."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The target file path."},
                "content": {"type": "string", "description": "The content to write."}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Make a precise string replacement in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The target file path."},
                "old_string": {"type": "string", "description": "The text to replace."},
                "new_string": {"type": "string", "description": "The replacement text."}
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "todo",
        "description": "Update task list. Track progress on multi-step tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "The numeric ID of this item."},
                            "text": {"type": "string", "description": "Description of the task."},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"], "description": "Current status of the item."}
                        },
                        "required": ["id", "text", "status"]
                    }
                }
            },
            "required": ["items"]
        }
    },
    {
        "name": "task",
        "description": "Delegate a focused, self-contained task to a subagent with fresh context. Use when the task is research/exploration (finding files, grepping, reading multiple files) or would require many sequential tool calls. Do NOT use for single-step actions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "agent_type": {
                    "type": "string",
                    "enum": ["explore", "general-purpose"],
                    "description": "explore = read-only (bash + read_file). general-purpose = full access."
                }
            },
            "required": ["prompt"]
        }
    },
    # TODO 1: 添加 load_skill 工具定义
    # 参考讲义 5.2 节，接受一个 name 参数
    {
        "name":"load_skill",
        "description":""
    }
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}
EXPLORE_TOOLS = [TOOLS_BY_NAME["bash"], TOOLS_BY_NAME["read_file"]]
GENERAL_TOOLS = [
    TOOLS_BY_NAME["bash"], TOOLS_BY_NAME["read_file"],
    TOOLS_BY_NAME["write_file"], TOOLS_BY_NAME["edit_file"],
]

# ============================================================================
# TOOL HANDLERS (unchanged from s04)
# ============================================================================

def tool_bash(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, timeout=timeout, text=True)
        return result.stdout or result.stderr or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


def tool_read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def tool_write_file(path: str, content: str) -> str:
    try:
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} characters to {path}."
    except Exception as e:
        return f"Error writing file {path}: {e}"


def tool_edit_file(path: str, old_string: str, new_string: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_string not in content:
            return f"Error: old_string not found in {path}"
        content = content.replace(old_string, new_string, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Edited {path} successfully."
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error editing file {path}: {e}"


class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        if len(items) > 20:
            raise ValueError("Too many todo items (max 20).")
        in_progress_count, validated = 0, []
        for item in items:
            if item["status"] not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {item['status']}")
            if not item.get("text"):
                raise ValueError("Todo text must not be empty.")
            if item["status"] == "in_progress":
                in_progress_count += 1
            validated.append(item)
        if in_progress_count > 1:
            raise ValueError("Only one item can be in_progress at a time.")
        self.items = validated
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "No todos."
        lines, done_count = [], 0
        for item in self.items:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(item["status"], "[ ]")
            if item["status"] == "completed":
                done_count += 1
            lines.append(f"{marker} #{item['id']} {item['text']}")
        lines.append(f"({done_count}/{len(self.items)} completed)")
        return "\n".join(lines)


todo_manager = TodoManager()


def todo_tool(items: list) -> str:
    try:
        return todo_manager.update(items)
    except ValueError as e:
        return str(e)


# ============================================================================
# SessionStore (from s03/s04, unchanged)
# ============================================================================

class SessionStore:
    """JSONL-based session storage."""

    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
    def _get_session_path(self, session_key: str) -> Path:
        return self.session_dir / f"{hashlib.md5(session_key.encode()).hexdigest()}.jsonl"

    def save_message(self, session_key: str, role: str, content, tool_use_id: str = None):
        file_path = self._get_session_path(session_key)
        serialized = self._serialize_content(content)
        message = {"timestamp": time.time(), "role": role, "content": serialized}
        if tool_use_id:
            message["tool_use_id"] = tool_use_id
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message) + "\n")

    def _serialize_content(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            result = []
            for c in content:
                if c.type == "text":
                    result.append({"type": "text", "text": c.text})
                elif c.type == "tool_use":
                    result.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
            return result

    def load_session(self, session_key: str) -> list:
        messages = []
        file_path = self._get_session_path(session_key)
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["role"] == "tool_result":
                        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": entry.get("tool_use_id"), "content": entry.get("content")}]})
                    else:
                        messages.append({"role": entry["role"], "content": entry["content"]})
        return messages

    def list_sessions(self) -> list:
        sessions = []
        for p in self.session_dir.glob("*.jsonl"):
            sessions.append({"key": p.stem, "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(), "size": p.stat().st_size})
        return sorted(sessions, key=lambda x: x["modified"], reverse=True)

    def delete_session(self, session_key: str):
        file_path = self._get_session_path(session_key)
        if file_path.exists():
            file_path.unlink()


# ============================================================================
# TOOL DISPATCH (s04 + s05)
# ============================================================================

TOOL_DICT = {
    "bash": tool_bash,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "edit_file": tool_edit_file,
    "todo": todo_tool,
    "task": lambda **kw: run_subagent(kw["prompt"], kw.get("agent_type", "explore")),
    # TODO: Register load_skill handler here
    # "load_skill": lambda **kw: SKILLS.___
}


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    handler = TOOL_DICT.get(tool_name)
    if handler is None:
        return f"Error: Unknown tool '{tool_name}'"
    return handler(**tool_input)


# ============================================================================
# run_subagent() (from s04, unchanged)
# ============================================================================

def run_subagent(prompt: str, agent_type: str = "explore") -> str:
    """Spawn a temporary agent with FRESH context. Returns a text summary."""
    if agent_type == "explore":
        sub_tools = EXPLORE_TOOLS
    else:
        sub_tools = GENERAL_TOOLS

    sub_handlers = {"bash": tool_bash, "read_file": tool_read_file}
    if agent_type != "explore":
        sub_handlers["write_file"] = tool_write_file
        sub_handlers["edit_file"] = tool_edit_file

    sub_messages = [{"role": "user", "content": prompt}]
    MAX_ROUNDS = 30
    resp = None

    try:
        for _ in range(MAX_ROUNDS):
            resp = client.messages.create(model=MODEL, messages=sub_messages, tools=sub_tools, max_tokens=8000)
            sub_messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                break
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    handler = sub_handlers.get(block.name)
                    tool_result = handler(**block.input) if handler else f"Error: Subagent tool '{block.name}' not available"
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": tool_result})
            sub_messages.append({"role": "user", "content": results})
    except Exception as e:
        return f"Subagent error: {e}"

    if resp:
        text_blocks = [b.text for b in resp.content if b.type == "text"]
        return "\n".join(text_blocks)
    return "(subagent produced no output)"


# ============================================================================
# TODO 1: SkillLoader Class
# ============================================================================

class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills = {}
        # TODO: 扫描 skills_dir, 解析 SKILL.md, 构建 self.skills 字典
        # 参考讲义 5.1 节

    def descriptions(self) -> str:
        # TODO: 返回 " - name: description\n" 格式的字符串
        pass

    def load(self, name: str) -> str:
        # TODO: 按名字查找, 返回 body 文本或错误信息
        pass

# ============================================================================
# TODO 2: Initialize Skills and update SYSTEM_PROMPT
# ============================================================================

SKILLS_DIR = WORKDIR / "skills"
SKILLS = SkillLoader(SKILLS_DIR)

SYSTEM_PROMPT = (
    "You are a coding agent. "
    "IMPORTANT: When you need to do research (find files, grep patterns, read multiple files, "
    "explore code structure), ALWAYS use the 'task' tool to delegate to a subagent. "
    "Do NOT use bash/read_file directly for research tasks. "
    "Only use direct tools for single-step actions."
    # TODO: Append available skills to the system prompt
    # Hint: use SKILLS.descriptions() and tell the model to use load_skill
    # f"... Skills available: {SKILLS.descriptions()} Use load_skill(name) to get instructions."
)


# ============================================================================
# Main Loop (from s04, with skills support)
# ============================================================================

def main():
    session_dir = os.path.join(os.path.dirname(__file__), "sessions_store")
    store = SessionStore(session_dir)

    print("\n=== Claw0 Agent (s05 - Skills) ===")
    print("Commands: /sessions, /new, /delete, /skills, quit\n")

    session_key = "default"
    messages = store.load_session(session_key)
    print(f"[{'Loaded' if messages else 'Started new'} session '{session_key}']\n")

    while True:
        try:
            user_input = input(f"[{session_key}] You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "q", "exit"):
                print("Goodbye!"); return
            if user_input.lower() == "/sessions":
                for s in store.list_sessions():
                    print(f"  {s['key']}  {s['modified']}  {s['size']} bytes")
                continue
            if user_input.lower().startswith("/delete"):
                parts = user_input.split()
                if len(parts) < 2:
                    print("Usage: /delete <session_key>"); continue
                store.delete_session(parts[1])
                print(f"[Deleted session '{parts[1]}']")
                continue
            if user_input.lower() == "/new":
                session_key = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                messages = store.load_session(session_key)
                print(f"[Started new session '{session_key}']")
                continue
            if user_input.lower() == "/skills":
                for name, skill in SKILLS.skills.items():
                    desc = skill["meta"].get("description", "(no description)")
                    print(f"  - {name}: {desc}")
                continue

            messages.append({"role": "user", "content": user_input})
            store.save_message(session_key, "user", user_input)

            rounds_since_todo = 0
            while True:
                response = client.messages.create(
                    model=MODEL, max_tokens=4096, system=SYSTEM_PROMPT,
                    messages=messages, tools=TOOLS
                )
                messages.append({"role": "assistant", "content": response.content})
                store.save_message(session_key, "assistant", response.content)

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if tool_use_blocks:
                    results, todo_called = [], False
                    for block in tool_use_blocks:
                        print(f"\n[Tool: {block.name}] Input: {json.dumps(block.input, indent=2)}")
                        tool_result = process_tool_call(block.name, block.input)
                        print(f"  Result: {tool_result[:200]}")
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": tool_result})
                        store.save_message(session_key, "tool_result", tool_result, block.id)
                        if block.name == "todo":
                            todo_called = True; rounds_since_todo = 0
                    if not todo_called:
                        rounds_since_todo += 1
                    if rounds_since_todo >= 3:
                        results.insert(0, {"type": "text", "text": "Update your todos."})
                    messages.append({"role": "user", "content": results})
                    continue
                else:
                    text = "\n".join(b.text for b in response.content if b.type == "text")
                    print(f"\nAgent > {text}\n")
                    break
        except KeyboardInterrupt:
            print("\n\nInterrupted."); break
        except Exception as e:
            print(f"\n[Error: {e}]\n")

if __name__ == "__main__":
    main()
