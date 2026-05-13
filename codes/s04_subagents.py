#!/usr/bin/env python3
"""
s04: Subagents -- "Fresh context for subtasks"

Extend s03 with a subagent system. The core idea:
spawn a disposable worker with fresh context, let it do focused work,
return a summary, and destroy it.

Key insight: subagents start with ZERO context from the parent.
They only get the prompt you send them.
"""

import os
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

client = anthropic.Anthropic(api_key=API_KEY, base_url=BASE_URL)

# ============================================================================
# TOOLS -- s03 tools + the new "task" tool for spawning subagents
# ============================================================================

TOOLS = [
    {
        "name": "bash",
        "description": "Execute a shell command and return the output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute."
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum wait time in seconds for command execution."
                }
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
                "path": {
                    "type": "string",
                    "description": "The path to the file to read."
                }
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
                "path": {
                    "type": "string",
                    "description": "The target file path."
                },
                "content": {
                    "type": "string",
                    "description": "The content to write."
                }
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
                "path": {
                    "type": "string",
                    "description": "The target file path."
                },
                "old_string": {
                    "type": "string",
                    "description": "The text to replace."
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement text."
                }
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
                            "id": {
                                "type": "integer",
                                "description": "The numeric ID of this item."
                            },
                            "text": {
                                "type": "string",
                                "description": "Description of the task."
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "Current status of the item."
                            }
                        },
                        "required": ["id", "text", "status"]
                    }
                }
            },
            "required": ["items"]
        }
    },
    # TODO: Add the "task" tool definition here
    # This tool tells the LLM: "When you need focused work, spawn a subagent."
    # It should have:
    #   - "prompt" (string, required): The task description for the subagent
    #   - "agent_type" (string, optional): "Explore" (read-only) or "general-purpose" (full access)
    {
        "name": "task",
        "description": "___DESCRIBE_WHEN_THE_LLM_SHOULD_USE_THIS___",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "agent_type": {
                    "type": "string",
                    # TODO: What are the valid agent_type values?
                    "enum": ["___", "___"],
                    "description": "___WHAT_DOES_EACH_TYPE_MEAN___"
                }
            },
            "required": ["___"]
        }
    }
]


# ============================================================================
# TOOL HANDLERS -- s03 handlers (unchanged)
# ============================================================================

def tool_bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, timeout=timeout, text=True)
        output = result.stdout or result.stderr
        if not output:
            output = "(command produced no output)"
        return output
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


def tool_read_file(path: str) -> str:
    """Read a file's contents."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def tool_write_file(path: str, content: str) -> str:
    """Write content to a file."""
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
    """Make a precise string replacement in a file."""
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


# ============================================================================
# TodoManager (from s03, unchanged)
# ============================================================================

class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        if len(items) > 20:
            raise ValueError("Too many todo items (max 20).")
        in_progress_count = 0
        validated = []
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
        lines = []
        done = 0
        for item in self.items:
            if item["status"] == "pending":
                marker = "[ ]"
            elif item["status"] == "in_progress":
                marker = "[>]"
            else:
                marker = "[x]"
                done += 1
            lines.append(f"{marker} #{item['id']} {item['text']}")
        lines.append(f"({done}/{len(self.items)} completed)")
        return "\n".join(lines)


todo_manager = TodoManager()


def todo_tool(items: list) -> str:
    try:
        return todo_manager.update(items)
    except ValueError as e:
        return str(e)


# ============================================================================
# TODO 1: SessionStore (from s03, unchanged -- you already implemented this)
# ============================================================================

class SessionStore:
    """JSONL-based session storage."""

    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_key: str) -> Path:
        hash_value = hashlib.md5(session_key.encode()).hexdigest()
        return self.session_dir / f"{hash_value}.jsonl"

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
        elif isinstance(content, list):
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
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": entry.get("tool_use_id"),
                                "content": entry.get("content")
                            }]
                        })
                    else:
                        messages.append({"role": entry["role"], "content": entry["content"]})
        return messages

    def list_sessions(self) -> list:
        sessions = []
        for p in self.session_dir.glob("*.jsonl"):
            sessions.append({
                "key": p.stem,
                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "size": p.stat().st_size
            })
        return sorted(sessions, key=lambda x: x["modified"], reverse=True)

    def delete_session(self, session_key: str):
        file_path = self._get_session_path(session_key)
        if file_path.exists():
            file_path.unlink()


# ============================================================================
# TOOL DISPATCH (from s03, plus the new "task" handler)
# ============================================================================

TOOL_DICT = {
    "bash": tool_bash,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "edit_file": tool_edit_file,
    "todo": todo_tool,
    # TODO: Register the "task" handler here
    # "task": lambda **kw: run_subagent(kw["prompt"], kw.get("agent_type", "___")),
}


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call to the appropriate handler."""
    handler = TOOL_DICT.get(tool_name)
    if handler is None:
        return f"Error: Unknown tool '{tool_name}'"
    return handler(**tool_input)


# ============================================================================
# TODO 2: run_subagent() -- The Core of s04
# ============================================================================

def run_subagent(prompt: str, agent_type: str = "Explore") -> str:
    """
    Spawn a temporary agent with FRESH context.
    Returns a text summary of what it found.

    Key idea: sub_messages starts with ONLY the prompt.
    No parent history leaks in.
    """
    # TODO: Define subagent tools based on agent_type
    # Explore mode: only bash + read_file (read-only exploration)
    # general-purpose: bash + read_file + write_file + edit_file
    if agent_type == "Explore":
        sub_tools = [
            # TODO: Add bash + read_file tool definitions
            # Hint: copy from TOOLS above, just the ones you need
        ]
    else:
        sub_tools = [
            # TODO: Add bash + read_file + write_file + edit_file
        ]

    # TODO: Define subagent tool handlers
    sub_handlers = {
        # "bash": tool_bash,
        # "read_file": tool_read_file,
        # "write_file": tool_write_file,  # only if not Explore
        # "edit_file": tool_edit_file,     # only if not Explore
    }

    # TODO: Create FRESH messages array -- this is the core idea of s04!
    sub_messages = [
        # TODO: What goes here? Just the user prompt.
        # The whole point is: subagent starts with ZERO parent context.
    ]

    MAX_ROUNDS = 30  # TODO: Why 30? What happens if this is too high?
    resp = None

    try:
        for round_num in range(MAX_ROUNDS):
            resp = client.messages.create(
                model=MODEL,
                messages=sub_messages,
                tools=sub_tools,
                max_tokens=8000
            )
            sub_messages.append({"role": "assistant", "content": resp.content})

            # TODO: Check stop_reason
            # If the LLM is NOT asking for tools, it's done (text response)
            if resp.stop_reason != "tool_use":
                break

            # TODO: Execute tool calls
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    handler = sub_handlers.get(block.name)
                    if handler:
                        tool_result = handler(**block.input)
                    else:
                        tool_result = f"Error: Subagent tool '{block.name}' not available"
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    })
            sub_messages.append({"role": "user", "content": results})

    except Exception as e:
        return f"Subagent error: {e}"

    # TODO: Extract final text from the last response
    # The LLM's last message might have text blocks -- join them all
    if resp:
        return "___"  # TODO: join all .text blocks from resp.content
    return "(subagent produced no output)"


# ============================================================================
# TODO 3: Main Loop (from s03, plus subagent support)
# ============================================================================

def main():
    session_dir = os.path.join(os.path.dirname(__file__), "sessions_store")
    store = SessionStore(session_dir)

    print("=== Claw0 Agent (s04 - Subagents) ===")
    print("Commands:")
    print("  /sessions - List all sessions")
    print("  /new      - Start a new session")
    print("  /delete <key> - Delete a session")
    print("  quit      - Exit")
    print()
    print("Try: 'Find all Python files with TODO comments'")
    print("     The agent should delegate this to a subagent via the 'task' tool.\n")

    session_key = "default"
    messages = store.load_session(session_key)
    if messages:
        print(f"[Loaded session '{session_key}' with {len(messages)} messages]\n")
    else:
        print(f"[Started new session '{session_key}']\n")

    while True:
        try:
            user_input = input(f"[{session_key}] You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "q", "exit"):
                print("Goodbye!")
                return
            if user_input.lower() == "/sessions":
                for s in store.list_sessions():
                    print(f"  {s['key']}  {s['modified']}  {s['size']} bytes")
                continue
            if user_input.lower().startswith("/delete"):
                parts = user_input.split()
                if len(parts) < 2:
                    print("Usage: /delete <session_key>")
                    continue
                store.delete_session(parts[1])
                print(f"[Deleted session '{parts[1]}']")
                continue
            if user_input.lower().startswith("/new"):
                session_key = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                messages = store.load_session(session_key)
                print(f"[Started new session '{session_key}']")
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})
            store.save_message(session_key, "user", user_input)

            rounds_since_todo = 0

            while True:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    messages=messages,
                    tools=TOOLS
                )
                messages.append({"role": "assistant", "content": response.content})
                store.save_message(session_key, "assistant", response.content)

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if tool_use_blocks:
                    results = []
                    todo_called = False
                    for block in tool_use_blocks:
                        print(f"\n[Tool: {block.name}]")
                        print(f"  Input: {json.dumps(block.input, indent=2)}")
                        tool_result = process_tool_call(block.name, block.input)
                        preview = tool_result[:200] if len(tool_result) > 200 else tool_result
                        print(f"  Result: {preview}")
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result
                        })
                        store.save_message(session_key, "tool_result", tool_result, block.id)
                        if block.name == "todo":
                            todo_called = True
                            rounds_since_todo = 0

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
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n[Error: {e}]\n")


if __name__ == "__main__":
    main()
