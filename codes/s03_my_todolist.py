 #!/usr/bin/env python3
"""
s03: Session Persistence - Remember Everything
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

# TODO: Copy TOOLS and handlers from s02
TOOLS = [
    {
        "name": "bash",
        "description":"Execute a shell command and return the output.",
        "input_schema":{
            "type":"object",
            "properties":{
                "command":{
                    "type": "string",
                    "description":"The shell command to execute."
                },
                "timeout":{
                    "type":"integer",
                    "description":"Longest waitting time for command execution."
                }
            },
            "required":["command"]
        }
    },
    {
        "name":"read_file",
        "description":"Read and return the file's contents.",
        "input_schema":{
            "type":"object",
            "properties":{
                "path":{
                    "type": "string",
                    "description":"the path to the file which is going to be read"
                }
            },
            "required":["path"]
        }
    },
    {
        "name":"write_file",
        "description":"write content to the file.",
        "input_schema":{
            "type":"object",
            "properties":{
                "path":{
                    "type":"string",
                    "description":"the target file to be written."
                },
                "content":{
                    "type":"string",
                    "description":"the content to be writen."
                }
            },
            "required":["path","content"]
        }
    },
    {
        "name":"edit_file",
        "description":"edit content in the specific path file",
        "input_schema":{
            "type":"object",
            "properties":{
                "path":{
                    "type":"string",
                    "description":"the specific path to the file."
                },
                "old_string":{
                    "type":"string",
                    "description":"the specific character to be replaced."
                },
                "new_string":{
                    "type":"string",
                    "description":"the target character to be replaced."
                }
            },
            "required":["path","old_string","new_string"]
        }
    },
    {
        "name": "todo",
        "description": "Update task list. Track progress on multi-step tasks. ",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id":{
                                "type": "integer",
                                "description":"the numberic id of the to do things"
                            },
                            "text":{
                                "type":"string",
                                "description":"what should to do for this task"
                            },
                            "status":{
                                "type": "string",
                                "description":"enums format value which consists of 'completed', 'in_progress','pending'"
                            }
                        },
                        "required": ["id", "text", "status"]
                    }
                }
            },
            "required": ["items"]
        }
    }
]
    

def tool_bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command."""
    try:
        # 使用subprocess方式执行shell命令
        result = subprocess.run(command,shell=True,capture_output=True,timeout=timeout,text=True)
        output = result.stdout or result.stderr
        if not output:
            output = "(command produced no output)"
        return output
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        print(f"exception is : {e}")
        return f"Error executing command: {e}"



def tool_read_file(path: str) -> str:
    """Read a file's contents."""
    # TODO: Implement with open()
    try:
        with open(path,encoding="utf-8") as f:
            lines = f.readlines()
            content = ''.join(lines)
            return content
    except FileNotFoundError:
        return f"Error: File not found {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def tool_write_file(path: str, content: str) -> str:
    """Write content to a file."""
    # TODO: Implement with open() and os.makedirs()
    try:
        # os.makedirs inside the try. 确保目标文件所在目录存在
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname,exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            return f"write to {path} {len(content)} characters."
    except Exception as e:
        return f"Error: write file {path} error {e}"


def tool_edit_file(path: str, old_string: str, new_string: str) -> str:
    """Make a precise string replacement in a file."""
    # TODO: Implement with string replacement
    try:
        with open(path,"r+",encoding="utf-8") as f:
            content = f.read()
            if old_string not in content:
                return f"Error: old_string is not found in this file"
            # content.replace不会反向赋值回去
            content = content.replace(old_string, new_string, 1)
            # f.seek(0)
            # f.truncate()
            # f.write(content)
            with open(path,"w", encoding="utf-8") as f:
                f.write(content)
            return content
    except FileNotFoundError:
        return f"Error: file{path} not found."
    except Exception as e:
        return f"Error: write file {path} error {e}"
            
class TodoManager:
    def __init__(self):
        # TODO: What state does this hold?
        self.items = []

    def update(self, items: list) -> str:
        """
        Accept a FULL replacement list (not a delta).
        Validate every item. If valid, store and return rendered view.
        If invalid, raise ValueError with a clear message.
        """
        if len(items) > 20:
            raise ValueError("plan items beyond 20, failed")
        in_progress_value, validated_items = 0, []
        for item in items:
            if item["status"] not in ["pending", "in_progress", "completed"]:
                raise ValueError("the status of plan item must be one of 'pending', 'in_progress', 'completed'")
            if not item.get("text"):
                raise ValueError("the text of plan item should not be empty.")
            if item["status"] == 'in_progress':
                in_progress_value += 1
            validated_items.append(item)
        if in_progress_value > 1:
            raise ValueError("the number of item status in_progress should not larger than 1")
        self.items = validated_items
        return self.render()

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
        if len(self.items) == 0:
            return "No todos."
        line, completed = "", 0
        for item in self.items:
            if item["status"] == "pending":
                line += "\n[ ] #"
            elif item["status"] == "in_progress":
                line += "\n[>] #"
            else:
                line += "\n[x] #"
                completed += 1
            line = line + str(item["id"]) + " " + item["text"]
        line += f"\n({completed}/{len(self.items)} completed)"
        return line
    
todo_manager = TodoManager()

def todo_tool(items:list) -> str:
    try:
        return todo_manager.update(items)
    except ValueError as e:
        return str(e)

TOOL_DICT = {
    "bash":tool_bash,
    "read_file":tool_read_file,
    "edit_file":tool_edit_file,
    "write_file":tool_write_file,
    "todo":todo_tool,
}

def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """
    Execute a tool call using the dispatch table.

    Returns the result as a string to send back to the model.
    """
    # TODO: Look up handler and execute it
    handler = TOOL_DICT.get(tool_name)
    if handler is None:
        return f"Error: Unknown tool {tool_name}"
    result = handler(**tool_input)
    return result


# ============================================================================
# TODO 1: SessionStore Class
# ============================================================================

class SessionStore:
    """JSONL-based session storage."""

    def __init__(self, session_dir: str):
        # TODO: Create directory if not exists
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True,exist_ok=True)

    def _get_session_path(self, session_key: str) -> Path:
        # TODO: Hash session key and return path
        hash_value = hashlib.md5(session_key.encode()).hexdigest()
        hash_path = self.session_dir / f"{hash_value}.jsonl"
        return hash_path


    def save_message(self, session_key: str, role: str, content, tool_use_id: str = None):
        # TODO: Append JSON line to file
        file_path = self._get_session_path(session_key=session_key)
        serialized_content = self._serialize_content(content=content)
        message = {
                'timestamp' : time.time(),
                'role' : role,
                'content': serialized_content
            }
        if tool_use_id:
            message["tool_use_id"] = tool_use_id
        message_json = json.dumps(message)
        with open(file_path,'a', encoding="utf-8") as f:
            f.write(message_json + '\n')


    def _serialize_content(self, content):
        # TODO: Handle both string and list (ContentBlock objects)
        if isinstance(content,str):
            return content
        elif isinstance(content,list):
            serialized = []
            for c in content:
                if c.type == 'text':
                    serialized.append({
                        'type':'text',
                        'text':c.text
                    })
                elif c.type == 'tool_use':
                    serialized.append({
                        'type':'tool_use',
                        'id':c.id,
                        'name':c.name,
                        'input':c.input
                    })
            return serialized

    def load_session(self, session_key: str) -> list:
        # TODO: Read JSONL, reconstruct messages for API
        messages = []
        file_path = self._get_session_path(session_key=session_key)
        if file_path.exists():
            with open(file_path,'r',encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["role"] == "tool_result":
                        messages.append({
                            "role":"user",
                            "content":[
                                {
                                    "type":"tool_result",
                                    "tool_use_id":entry.get("tool_use_id"),
                                    "content":entry.get("content")
                                }
                            ]
                        })
                    else:
                        messages.append({
                            "role":entry.get("role"),
                            "content":entry.get("content")
                        })
        return messages



    def list_sessions(self) -> list:
        # TODO: Return list of available sessions
        sessions = []
        for path in self.session_dir.glob("*.jsonl"):
            sessions.append({
                "key":path.stem,
                "modified":datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "size":path.stat().st_size
            })
        return sorted(sessions,key= lambda x : x.get("modified"),reverse=True)

        

    def delete_session(self, session_key: str):
        # TODO: Delete session file
        file_path = self._get_session_path(session_key=session_key)
        if file_path.exists():
            file_path.unlink()




# ============================================================================
# TODO 2: Main Loop with Persistence
# ============================================================================

def main():
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    model_name = os.getenv("ANTHROPIC_MODEL")

    # TODO: Create client and SessionStore
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url
    )

    session_dir = os.path.join(os.path.dirname(__file__),"sessions_store")
    store = SessionStore(session_dir)

    print("=== Claw0 Agent (s03 - Session Persistence) ===")
    print("Commands:")
    print("  /sessions - List all sessions")
    print("  /new - Start a new session")
    print("  /delete <key> - Delete a session")
    print("  quit - Exit\n")

    # TODO: Default session key
    session_key = "default"
    # TODO: Load existing session
    messages = store.load_session(session_key)
    if messages:
        print(f"[Loaded session '{session_key}' with {len(messages)} messages]\n")
    else:
        print(f"[started new session '{session_key}']\n")

    # TODO: Outer loop with commands
    while True:
        try:
            user_input = input(f"[{session_key}] You > ").strip()
            # 处理空输入
            if not user_input:
                continue
            # 处理quit
            if user_input.lower() in ["quit","q","exit"]:
                print("Good bye")
                return
            if user_input.lower() == "/sessions":
                sessions = store.list_sessions()
                print("Avaliable sessions: ")
                for session in sessions:
                    print(f"session key: {session['key']} - {session['modified']} - {session['size']} bytes")
                continue
            elif user_input.lower().startswith("/delete"):
                parts = user_input.split()
                if len(parts) < 2:
                    print("[Usage: /delete <session_key>]")
                    continue
                session_name = parts[1]
                store.delete_session(session_name)
                print(f"[Deleted session '{session_name}']")
                continue
            elif user_input.lower().startswith("/new"):
                new_session_key = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                messages = store.load_session(new_session_key)
                print(f"[Started new session '{new_session_key}']")
                session_key = new_session_key
                continue
            
            messages.append({
                "role":"user",
                "content":user_input
            })
            store.save_message(session_key,"user",user_input)

            rounds_since_todo = 0

            while True:
                response = client.messages.create(
                        model=model_name,
                        max_tokens=4096,
                        messages=messages,
                        tools=TOOLS
                )
                # save + append assistant response
                messages.append({"role": "assistant", "content": response.content})
                store.save_message(session_key, "assistant", response.content)

                # check for tool_use blocks
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if tool_use_blocks:
                    results = []
                    todo_called = False
                    for block in tool_use_blocks:
                        print(f"\n[Tool: {block.name}]")
                        print(f"\nInput: {block.input}\n")
                        tool_use_result = process_tool_call(tool_name=block.name, tool_input=block.input)
                        print(f"  Result: {tool_use_result[:200]}")
                        # add tool result message
                        results.append(
                            {
                                "type":"tool_result",
                                "tool_use_id":block.id,
                                "content":tool_use_result
                            }
                        )
                        store.save_message(session_key,"tool_result",tool_use_result,block.id)
                        if block.name == "todo":
                            todo_called = True
                            rounds_since_todo = 0
                    
                    if not todo_called:
                        rounds_since_todo += 1
                    if rounds_since_todo >= 3:
                        results.insert(0,{
                            "type":"text",
                            "text":"Update your todos"
                        })
                    messages.append({'role':"user","content":results})
                    continue
                else:
                    # text response, print and break
                    text = "\n".join(b.text for b in response.content if b.type == "text")
                    print(f"\nAgent > {text}\n")
                    break  # ← exit inner loop, back to outer loop for next user input
    
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        
        except Exception as e:
            print(f"\n[Error: {e}]\n")
    
if __name__ == "__main__":
    main()