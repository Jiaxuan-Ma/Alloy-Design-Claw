"""
LangChain Agent + Skills system.
Designed for use in Jupyter Notebook.

Usage example:
    from base_agent import scan_skills, initialize_agent, chat

    # 1. Scan Skills
    skills_snapshot = scan_skills(Path("./skills"))

    # 2. Initialize the Agent
    agent = initialize_agent(
        api_key="sk-xxx",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        skills_dir=Path("./skills")
    )

    # 3. Chat
    response = chat(agent, "Check the weather in Beijing")
    print(response)

    # 4. Streaming chat
    async for chunk in chat_stream(agent, "Check the weather in Beijing"):
        print(chunk, end="", flush=True)

Dependency versions:
    langchain==1.2.12
    langchain-core==1.2.19
    langchain-deepseek==1.0.1
    pyyaml
    requests
    html2text
"""

import os
import subprocess
from pathlib import Path
from typing import Any, AsyncGenerator, List, Dict, Type

import yaml
import requests
import html2text
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

DEFAULT_AGENT_PYTHON = Path(r"D:\anaconda3\envs\pytorch_gpu\python.exe")


def get_agent_python() -> str:
    configured = os.getenv("AGENT_PYTHON") or os.getenv("PYTORCH_GPU_PYTHON")
    if configured:
        return str(Path(configured))
    if DEFAULT_AGENT_PYTHON.exists():
        return str(DEFAULT_AGENT_PYTHON)
    return "python"


def normalize_python_command(command: str) -> str:
    stripped = command.lstrip()
    prefix = command[: len(command) - len(stripped)]
    lowered = stripped.lower()
    if lowered == "python" or lowered.startswith("python "):
        return f'{prefix}"{get_agent_python()}"{stripped[6:]}'
    if lowered == "python.exe" or lowered.startswith("python.exe "):
        return f'{prefix}"{get_agent_python()}"{stripped[10:]}'
    return command


# ============ Skills Scanning ============
# Extracted from: tools/skills_scanner.py

def scan_skills(skills_dir: Path) -> str:
    """
    Scan all SKILL.md files under the skills/ directory and parse YAML frontmatter.

    Args:
        skills_dir: Path to the skills directory.

    Returns:
        Skills snapshot as an XML-formatted string.

    Example output:
        <available_skills>
          <skill>
            <name>get_weather</name>
            <description>Get weather information for a specified city</description>
            <location>./skills/get_weather/SKILL.md</location>
          </skill>
        </available_skills>
    """
    if not skills_dir.exists():
        skills_dir.mkdir(parents=True)
        return "<available_skills>\n</available_skills>"

    skills = []
    # Iterate over all SKILL.md files under the skills directory.
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        try:
            content = skill_md.read_text(encoding="utf-8")
            # Parse the YAML metadata at the top (format: ---\nkey: value\n---).
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1])
                    if meta:
                        # Compute the relative path for the Agent to read.
                        rel_path = str(skill_md.relative_to(skills_dir.parent))
                        skills.append({
                            "name": meta.get("name", skill_md.parent.name),
                            "description": meta.get("description", ""),
                            "location": rel_path,
                        })
        except Exception as e:
            print(f" Error scanning {skill_md}: {e}")

    # Assemble the extracted skill information into XML for the model prompt.
    lines = ["<available_skills>"]
    for s in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{s['name']}</name>")
        lines.append(f"    <description>{s['description']}</description>")
        lines.append(f"    <location>{s['location']}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")

    snapshot = "\n".join(lines)
    print(f"Skills snapshot: {len(skills)} skills found")
    return snapshot


# ============ System Prompt Construction ============

def build_system_prompt(skills_snapshot: str) -> str:
    """
    Build the simplified system prompt.

    Args:
        skills_snapshot: XML-formatted snapshot returned by scan_skills().

    Returns:
        Complete system prompt string.
    """
    base_prompt = """你是一个专业的 AI 助手，拥有工具调用能力。

    ## 可用技能
    {skills_snapshot}

    ## 技能调用协议
    当你需要使用某个技能时，必须：
    1. 先使用 read_file 工具读取技能定义文件（location 字段指定的路径）
    2. 仔细阅读 SKILL.md 中的执行步骤
    3. 根据步骤调用相应的工具（fetch_url、terminal 等）

    禁止直接猜测技能用法，必须先读取文件！

    ## 工具使用规范
    - read_file: 读取本地文件（相对于项目根目录）
    - fetch_url: 获取网页内容
    - terminal: 执行 Shell 命令（沙箱限制）

    ## 默认运行环境
    - 当前项目的默认 Python/TC-Python 环境是 `D:\\anaconda3\\envs\\pytorch_gpu\\python.exe`。
    - 运行任何 Python 脚本时，直接使用该环境；不要再搜索、枚举或切换其他 Conda 环境。
    - 当执行 Thermo-Calc/TC-Python 相关脚本时，也默认使用 `pytorch_gpu` 环境，除非用户明确要求检查其他环境。
    - 如果需要确认 TC-Python，只允许用 `python -c "import tc_python; print(tc_python.__version__)"` 做一次快速验证；不要进行多环境扫描。

    ## 重要提醒
    - 必须使用工具来完成任务，不要只在文本中描述操作
    - 需要读取文件时调用 read_file，需要执行命令时调用 terminal
    - 工具调用失败时，分析错误原因并重试
    """
    return base_prompt.format(skills_snapshot=skills_snapshot)


# ============ Tool Definitions ============
# Extracted from: tools/read_file_tool.py

# Define the data input schema for the file-reading tool.
class ReadFileInput(BaseModel):
    # file_path requires the model to provide a target file path for read tasks.
    # The path must be relative to the project root to avoid sandbox errors.
    file_path: str = Field(
        description="Relative path of the file to read (relative to project root)"
    )


class SandboxedReadFileTool(BaseTool):
    """Sandboxed file-reading tool restricted to the project root."""
    name: str = "read_file"
    description: str = (
        "Read the content of a local file. Path is relative to the project root. "
        "Use this to read SKILL.md files, configuration files, etc. "
        "Example: read_file('skills/get_weather/SKILL.md')"
    )
    args_schema: Type[BaseModel] = ReadFileInput
    root_dir: str = ""

    def _run(self, file_path: str) -> str:
        try:
            root = Path(self.root_dir)
            # Normalize the path to remove backslashes and redundant ./ prefixes.
            normalized = file_path.replace("\\", "/").lstrip("./")
            full_path = (root / normalized).resolve()

            # Sandbox guard: keep the resolved path under the project root.
            if not str(full_path).startswith(str(root.resolve())):
                return f" Access denied: path escapes project root"

            if not full_path.exists():
                return f" File not found: {file_path}"

            if not full_path.is_file():
                return f" Not a file: {file_path}"

            content = full_path.read_text(encoding="utf-8")
            # Limit file content to avoid overflowing the model context.
            if len(content) > 10000:
                content = content[:10000] + "\n...[truncated]"
            return content

        except Exception as e:
            return f" Error reading file: {str(e)}"


def create_read_file_tool(base_dir: Path) -> SandboxedReadFileTool:
    """Create a read_file tool instance."""
    return SandboxedReadFileTool(root_dir=str(base_dir))


# ============ Fetch URL Tool ============
# Extracted from: tools/fetch_url_tool.py

# Define the tool input schema.
# It must inherit from BaseModel so LangChain can expose it as JSON schema.
class FetchURLInput(BaseModel):
    # url is the required string parameter for this tool.
    # The description helps the model extract the URL from the chat context.
    url: str = Field(description="The URL to fetch content from")

class FetchURLTool(BaseTool):
    """Fetch web page content and convert it to Markdown."""
    name: str = "fetch_url"
    description: str = (
        "Fetch the content of a web page and return it as cleaned Markdown text. "
        "Use this to retrieve information from the internet. "
        "Input should be a valid URL (starting with http:// or https://)."
    )
    args_schema: Type[BaseModel] = FetchURLInput

    def _run(self, url: str) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; StandaloneAgent/0.1)"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")

            # JSON is common for APIs; keep the raw text format.
            if "application/json" in content_type:
                text = resp.text
                if len(text) > 5000:
                    text = text[:5000] + "\n...[truncated]"
                return text

            # For regular HTML pages, extract text as Markdown and drop styling tags.
            # This preserves useful information while reducing token usage.
            converter = html2text.HTML2Text()
            converter.ignore_links = False    # Keep links because they may be useful to the model.
            converter.ignore_images = True    # Ignore images.
            converter.body_width = 0
            markdown = converter.handle(resp.text)

            # Prevent overly long web page content.
            if len(markdown) > 5000:
                markdown = markdown[:5000] + "\n...[truncated]"
            return markdown

        except requests.Timeout:
            return "❌ Request timed out (15s limit)"
        except requests.RequestException as e:
            return f"❌ Fetch error: {str(e)}"


def create_fetch_url_tool() -> FetchURLTool:
    """Create a fetch_url tool instance."""
    return FetchURLTool()


# ============ Terminal Tool ============
# Extracted from: tools/terminal_tool.py

# Dangerous command blacklist.
BLACKLISTED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "format c:",
    "del /f /s /q c:",
]


# Define the input schema for the terminal command execution tool.
class TerminalInput(BaseModel):
    # command requires the model to provide the shell command in this field.
    # The Field description tells the model where to place the shell command string.
    command: str = Field(description="The shell command to execute")


class SafeTerminalTool(BaseTool):
    """Sandboxed shell command execution tool."""
    name: str = "terminal"
    description: str = (
        "Execute shell commands in a sandboxed environment. "
        "The working directory is restricted to the project root. "
        "Use this for file operations, installing packages, running scripts, etc. "
        "Python commands are normalized to D:\\anaconda3\\envs\\pytorch_gpu\\python.exe."
    )
    args_schema: Type[BaseModel] = TerminalInput
    root_dir: str = ""

    def _is_safe(self, command: str) -> bool:
        """Check whether the command matches the blacklist."""
        cmd_lower = command.lower().strip()
        for blocked in BLACKLISTED_COMMANDS:
            if blocked in cmd_lower:
                return False
        return True

    def _run(self, command: str) -> str:
        command = normalize_python_command(command)
        # Apply blacklist filtering before execution.
        if not self._is_safe(command):
            return f"❌ Command blocked for safety: {command}"
        try:
            # Execute the shell command with a longer timeout for benchmark-like tasks.
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=1800,
                encoding="utf-8",
                errors="replace",
            )
            # Collect standard output.
            output = result.stdout
            # Merge standard error into the output returned to the model.
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if not output.strip():
                output = "(command completed with no output)"
                
            # Limit command output size to avoid excessive logs.
            if len(output) > 5000:
                output = output[:5000] + "\n...[truncated]"
            return output
        except subprocess.TimeoutExpired:
            return "❌ Command timed out (1800s limit)"
        except Exception as e:
            return f"❌ Error: {str(e)}"


def create_terminal_tool(base_dir: Path) -> SafeTerminalTool:
    """Create a terminal tool instance."""
    return SafeTerminalTool(root_dir=str(base_dir))


# ============ Agent Initialization ============
# Extracted from: graph/agent.py (simplified version)

def initialize_agent(
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    temperature: float = 0.7,
    skills_dir: Path = None,
    base_dir: Path = None
):
    """
    Initialize the LangChain Agent.

    Args:
        api_key: DeepSeek API Key
        base_url: API base URL.
        model: Model name.
        temperature: Sampling temperature (0-1).
        skills_dir: Path to the skills directory for skill scanning.
        base_dir: Project root directory used by sandboxed tools.

    Returns:
        LangChain Agent instance.

    Example:
        agent = initialize_agent(
            api_key="sk-xxx",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            skills_dir=Path("./skills"),
            base_dir=Path(".")
        )
    """
    
    # Use the current directory when base_dir is not provided.
    if base_dir is None:
        base_dir = Path.cwd()

    # Use base_dir/skills when skills_dir is not provided.
    if skills_dir is None:
        skills_dir = base_dir / "skills"

    # 1. Scan all local skills and generate XML for the model.
    skills_snapshot = scan_skills(skills_dir)

    # 2. Embed the skill snapshot into the system prompt.
    system_prompt = build_system_prompt(skills_snapshot)

    # 3. Prepare the core tools: file reading, web fetching, and command execution.
    tools = [
        create_read_file_tool(base_dir),
        create_fetch_url_tool(),
        create_terminal_tool(base_dir),
    ]

    # 4. Initialize the DeepSeek chat model.
    llm = ChatDeepSeek(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        streaming=True,
        timeout=180,
        max_retries=3,
    )

    # 5. Assemble a runnable Agent from the model, tools, and system prompt.
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )

    print(f"🤖 Agent initialized with {len(tools)} tools (model: {model})")
    return agent


# ============ Chat Interface ============
# Extracted from: graph/agent.py (simplified version)

def chat(
    agent,
    message: str,
    history: List[Dict[str, str]] = None
) -> str:
    """
    Synchronous chat that returns the complete response.

    Args:
        agent: Agent instance returned by initialize_agent().
        message: User message.
        history: Conversation history in the format [{"role": "user", "content": "..."}, ...].

    Returns:
        Complete response text from the Agent.

    Example:
        response = chat(agent, "Check the weather in Beijing")
        print(response)
    """
    if history is None:
        history = []

    # Build the message list.
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=message))

    # Invoke the Agent.
    result = agent.invoke({"messages": messages})

    # Extract the last AI message.
    final_messages = result.get("messages", [])
    for msg in reversed(final_messages):
        if hasattr(msg, "content") and msg.type == "ai" and msg.content:
            return msg.content

    return "No response generated."


async def chat_stream(
    agent,
    message: str,
    history: List[Dict[str, str]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streaming chat that yields tokens and tool events.

    Args:
        agent: Agent instance returned by initialize_agent().
        message: User message.
        history: Conversation history.

    Yields:
        Event dictionaries with the following types:
        - {"type": "token", "content": "..."}  # Text token
        - {"type": "tool_start", "tool": "...", "input": "..."}  # Tool call started
        - {"type": "tool_end", "tool": "...", "output": "..."}  # Tool call ended
        - {"type": "done", "content": "..."}  # Complete response

    Example:
        async for event in chat_stream(agent, "Check the weather in Beijing"):
            if event["type"] == "token":
                print(event["content"], end="", flush=True)
            elif event["type"] == "tool_start":
                print(f"\n[Calling tool: {event['tool']}]")
            elif event["type"] == "tool_end":
                print(f"[Tool output: {event['output'][:100]}...]")
    """
    if history is None:
        history = []

    # Convert dictionary-style conversation history into LangChain message objects.
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    # Append the latest user message.
    messages.append(HumanMessage(content=message))

    full_response = ""

    # Use astream to listen for and forward events from the Agent.
    # stream_mode=["messages", "updates"] returns both text generation and tool status.
    async for event in agent.astream(
        {"messages": messages},
        stream_mode=["messages", "updates"],
    ):
        # The event may be a (stream_mode, data) tuple.
        if isinstance(event, tuple):
            mode, data = event
        else:
            mode = "messages"
            data = event

        # In messages mode, the model is streaming visible chat text.
        if mode == "messages":
            msg, metadata = data
            if hasattr(msg, "content") and msg.content:
                # Filter out hidden tool-call instructions and yield normal chat text only.
                if msg.type == "AIMessageChunk" or msg.type == "ai":
                    if msg.content and not getattr(msg, "tool_calls", None):
                        full_response += msg.content
                        yield {"type": "token", "content": msg.content}

        # In updates mode, larger state changes occur, such as tool calls and tool results.
        elif mode == "updates":
            if isinstance(data, dict):
                for node_name, node_data in data.items():
                    # A tool has just finished executing.
                    if node_name == "tools" and "messages" in node_data:
                        for tool_msg in node_data["messages"]:
                            if hasattr(tool_msg, "name"):
                                yield {
                                    "type": "tool_end",
                                    "tool": tool_msg.name,
                                    "output": str(tool_msg.content)[:2000],
                                }
                    # The model has requested a new tool call.
                    elif node_name == "model" and "messages" in node_data:
                        for agent_msg in node_data["messages"]:
                            if hasattr(agent_msg, "tool_calls") and agent_msg.tool_calls:
                                for tc in agent_msg.tool_calls:
                                    yield {
                                        "type": "tool_start",
                                        "tool": tc["name"],
                                        "input": str(tc.get("args", ""))[:1000],
                                    }

    # When the conversation ends, send the assembled final response.
    yield {"type": "done", "content": full_response}


# ============ Test Code ============

if __name__ == "__main__":
    import asyncio

    # Test Skills scanning.
    print("=== 测试 Skills 扫描 ===")
    test_skills_dir = Path("./skills")
    if test_skills_dir.exists():
        snapshot = scan_skills(test_skills_dir)
        print(snapshot)
    else:
        print("⚠️ skills/ 目录不存在，跳过扫描测试")

    # Test Agent initialization, which requires an API key.
    print("\n=== 测试 Agent 初始化 ===")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        agent = initialize_agent(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            base_dir=Path(".")
        )

        # Test synchronous chat.
        print("\n=== 测试同步对话 ===")
        response = chat(agent, "你好，请介绍一下你自己")
        print(f"Response: {response}")

        # Test streaming chat.
        print("\n=== 测试流式对话 ===")
        async def test_stream():
            async for event in chat_stream(agent, "1+1等于几？"):
                if event["type"] == "token":
                    print(event["content"], end="", flush=True)
                elif event["type"] == "done":
                    print(f"\n\n完整响应: {event['content']}")

        asyncio.run(test_stream())
    else:
        print("⚠️ 未设置 DEEPSEEK_API_KEY 环境变量，跳过 Agent 测试")
