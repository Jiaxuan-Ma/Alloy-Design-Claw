"""
简化版 LangChain Agent + Skills 系统
适合在 Jupyter Notebook 中使用

使用示例:
    from base_agent import scan_skills, initialize_agent, chat

    # 1. 扫描 Skills
    skills_snapshot = scan_skills(Path("./skills"))

    # 2. 初始化 Agent
    agent = initialize_agent(
        api_key="sk-xxx",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        skills_dir=Path("./skills")
    )

    # 3. 对话
    response = chat(agent, "查询北京的天气")
    print(response)

    # 4. 流式对话
    async for chunk in chat_stream(agent, "查询北京的天气"):
        print(chunk, end="", flush=True)

依赖版本:
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


# ============ Skills 扫描 ============
# 提取自: tools/skills_scanner.py

def scan_skills(skills_dir: Path) -> str:
    """
    扫描 skills/ 目录下的所有 SKILL.md 文件，解析 YAML frontmatter

    Args:
        skills_dir: skills 目录路径

    Returns:
        XML 格式的 skills 快照字符串

    示例输出:
        <available_skills>
          <skill>
            <name>get_weather</name>
            <description>查询指定城市的天气信息</description>
            <location>./skills/get_weather/SKILL.md</location>
          </skill>
        </available_skills>
    """
    if not skills_dir.exists():
        skills_dir.mkdir(parents=True)
        return "<available_skills>\n</available_skills>"

    skills = []
    # 遍历 skills 目录下的所有 SKILL.md 文件
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        try:
            content = skill_md.read_text(encoding="utf-8")
            # 解析顶部的 YAML 元数据 (格式: ---\nkey: value\n---)
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1])
                    if meta:
                        # 计算相对路径，供 Agent 读取
                        rel_path = str(skill_md.relative_to(skills_dir.parent))
                        skills.append({
                            "name": meta.get("name", skill_md.parent.name),
                            "description": meta.get("description", ""),
                            "location": rel_path,
                        })
        except Exception as e:
            print(f" Error scanning {skill_md}: {e}")

    # 将提取到的技能信息组装成 XML 格式，这段 XML 最终会喂给大模型作为提示词
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


# ============ System Prompt 构建 ============

def build_system_prompt(skills_snapshot: str) -> str:
    """
    构建简化版 System Prompt

    Args:
        skills_snapshot: scan_skills() 返回的 XML 格式快照

    Returns:
        完整的 system prompt 字符串
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


# ============ 工具定义 ============
# 提取自: tools/read_file_tool.py

# 定义“文件读取工具”的数据输入格式（Schema）
class ReadFileInput(BaseModel):
    # file_path: 强制大模型在指派读取任务时，必须提供一个目标文件的路径
    # 明确告诉它“这里的路径必须是相对于项目根目录的相对路径”，避免它乱猜绝对路径导致沙箱报错
    file_path: str = Field(
        description="Relative path of the file to read (relative to project root)"
    )


class SandboxedReadFileTool(BaseTool):
    """沙箱化的文件读取工具，限制在项目根目录内"""
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
            # 整理路径，防止出现反斜杠或多余的 ./
            normalized = file_path.replace("\\", "/").lstrip("./")
            full_path = (root / normalized).resolve()

            # 沙箱机制：确保最终解析的路径仍然在项目根目录下，防止 ".." 越权读取系统文件
            if not str(full_path).startswith(str(root.resolve())):
                return f" Access denied: path escapes project root"

            if not full_path.exists():
                return f" File not found: {file_path}"

            if not full_path.is_file():
                return f" Not a file: {file_path}"

            content = full_path.read_text(encoding="utf-8")
            # 为了防止把大模型的上下文撑爆，限制读取前 10000 个字符
            if len(content) > 10000:
                content = content[:10000] + "\n...[truncated]"
            return content

        except Exception as e:
            return f" Error reading file: {str(e)}"


def create_read_file_tool(base_dir: Path) -> SandboxedReadFileTool:
    """创建 read_file 工具实例"""
    return SandboxedReadFileTool(root_dir=str(base_dir))


# ============ Fetch URL 工具 ============
# 提取自: tools/fetch_url_tool.py

# 定义工具的数据输入格式（Schema）
# 必须继承 BaseModel，这样 LangChain 才能把它翻译成大模型能看懂的 JSON 格式说明书
class FetchURLInput(BaseModel):
    # url: 强制规定调用此工具必须传入名为 "url" 的字符串参数
    # 大模型看到这段描述后，就会知道要从用户的聊天内容中提取出网页链接填到这里
    url: str = Field(description="The URL to fetch content from")

class FetchURLTool(BaseTool):
    """获取网页内容并转换为 Markdown"""
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

            # API 常见的返回格式是 JSON，直接保留文本格式即可
            if "application/json" in content_type:
                text = resp.text
                if len(text) > 5000:
                    text = text[:5000] + "\n...[truncated]"
                return text

            # 对于普通网页 (HTML)，抽取其中的纯文本内容转为 Markdown，舍弃复杂的样式标签
            # 这样能有效提取信息并减少 Token 消耗
            converter = html2text.HTML2Text()
            converter.ignore_links = False    # 保留网页链接，可能对大模型有用
            converter.ignore_images = True    # 忽略图片
            converter.body_width = 0
            markdown = converter.handle(resp.text)

            # 防止网页内容过长
            if len(markdown) > 5000:
                markdown = markdown[:5000] + "\n...[truncated]"
            return markdown

        except requests.Timeout:
            return "❌ Request timed out (15s limit)"
        except requests.RequestException as e:
            return f"❌ Fetch error: {str(e)}"


def create_fetch_url_tool() -> FetchURLTool:
    """创建 fetch_url 工具实例"""
    return FetchURLTool()


# ============ Terminal 工具 ============
# 提取自: tools/terminal_tool.py

# 危险命令黑名单
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


# 定义“终端命令执行工具”的数据输入格式（Schema）
class TerminalInput(BaseModel):
    # command: 规定大模型如果想执行系统命令，必须把命令写在这个字段里
    # Field 里的说明书明确告诉大模型：“把你写好的底层 shell 脚本/命令字符串放这儿”
    command: str = Field(description="The shell command to execute")


class SafeTerminalTool(BaseTool):
    """沙箱化的 Shell 命令执行工具"""
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
        """检查命令是否在黑名单中"""
        cmd_lower = command.lower().strip()
        for blocked in BLACKLISTED_COMMANDS:
            if blocked in cmd_lower:
                return False
        return True

    def _run(self, command: str) -> str:
        command = normalize_python_command(command)
        # 先进行黑名单匹配过滤
        if not self._is_safe(command):
            return f"❌ Command blocked for safety: {command}"
        try:
            # 执行 shell 命令，benchmark 等长时任务需要较长超时
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
            # 收集标准输出
            output = result.stdout
            # 收集错误输出，合并在一起发回给模型
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if not output.strip():
                output = "(command completed with no output)"
                
            # 控制命令返回大小，防止日志太长撑爆系统
            if len(output) > 5000:
                output = output[:5000] + "\n...[truncated]"
            return output
        except subprocess.TimeoutExpired:
            return "❌ Command timed out (1800s limit)"
        except Exception as e:
            return f"❌ Error: {str(e)}"


def create_terminal_tool(base_dir: Path) -> SafeTerminalTool:
    """创建 terminal 工具实例"""
    return SafeTerminalTool(root_dir=str(base_dir))


# ============ Agent 初始化 ============
# 提取自: graph/agent.py (简化版)

def initialize_agent(
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    temperature: float = 0.7,
    skills_dir: Path = None,
    base_dir: Path = None
):
    """
    初始化 LangChain Agent

    Args:
        api_key: DeepSeek API Key
        base_url: API 基础 URL
        model: 模型名称
        temperature: 温度参数 (0-1)
        skills_dir: skills 目录路径（用于扫描技能）
        base_dir: 项目根目录（用于工具沙箱）

    Returns:
        LangChain Agent 实例

    示例:
        agent = initialize_agent(
            api_key="sk-xxx",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            skills_dir=Path("./skills"),
            base_dir=Path(".")
        )
    """
    
    # 如果未指定 base_dir，使用当前目录
    if base_dir is None:
        base_dir = Path.cwd()

    # 如果未指定 skills_dir，使用 base_dir/skills
    if skills_dir is None:
        skills_dir = base_dir / "skills"

    # 1. 扫描出本地现有的所有技能，生成 XML 供大模型识别
    skills_snapshot = scan_skills(skills_dir)

    # 2. 将技能快照嵌入到系统提示词中，告知大模型它能做什么
    system_prompt = build_system_prompt(skills_snapshot)

    # 3. 准备三大基础工具对象（读取文件、请求网页、执行命令）
    tools = [
        create_read_file_tool(base_dir),
        create_fetch_url_tool(),
        create_terminal_tool(base_dir),
    ]

    # 4. 初始化模型对象，这里特指 DeepSeek 对话模型
    llm = ChatDeepSeek(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        streaming=True,
        timeout=180,
        max_retries=3,
    )

    # 5. 使用大模型 + 工具箱 + 系统提示词 共同组装成一个可以独立运行的 Agent
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )

    print(f"🤖 Agent initialized with {len(tools)} tools (model: {model})")
    return agent


# ============ 对话接口 ============
# 提取自: graph/agent.py (简化版)

def chat(
    agent,
    message: str,
    history: List[Dict[str, str]] = None
) -> str:
    """
    同步对话（返回完整响应）

    Args:
        agent: initialize_agent() 返回的 Agent 实例
        message: 用户消息
        history: 历史对话记录，格式: [{"role": "user", "content": "..."}, ...]

    Returns:
        Agent 的完整响应文本

    示例:
        response = chat(agent, "查询北京的天气")
        print(response)
    """
    if history is None:
        history = []

    # 构建消息列表
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=message))

    # 调用 Agent
    result = agent.invoke({"messages": messages})

    # 提取最后一条 AI 消息
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
    流式对话（逐 token 返回）

    Args:
        agent: initialize_agent() 返回的 Agent 实例
        message: 用户消息
        history: 历史对话记录

    Yields:
        事件字典，包含以下类型:
        - {"type": "token", "content": "..."}  # 文本 token
        - {"type": "tool_start", "tool": "...", "input": "..."}  # 工具调用开始
        - {"type": "tool_end", "tool": "...", "output": "..."}  # 工具调用结束
        - {"type": "done", "content": "..."}  # 完整响应

    示例:
        async for event in chat_stream(agent, "查询北京的天气"):
            if event["type"] == "token":
                print(event["content"], end="", flush=True)
            elif event["type"] == "tool_start":
                print(f"\n[调用工具: {event['tool']}]")
            elif event["type"] == "tool_end":
                print(f"[工具输出: {event['output'][:100]}...]")
    """
    if history is None:
        history = []

    # 将普通字典格式的对话历史，转化为 Langchain 组件理解的消息对象
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    # 加入用户最新的消息
    messages.append(HumanMessage(content=message))

    full_response = ""

    # 使用 astream 监听并推送 Agent 内发生的事件
    # stream_mode=["messages", "updates"] 会同时返回 "文本字符生成" 和 "调用工具状态"
    async for event in agent.astream(
        {"messages": messages},
        stream_mode=["messages", "updates"],
    ):
        # event 可能是 (stream_mode, data) 元组
        if isinstance(event, tuple):
            mode, data = event
        else:
            mode = "messages"
            data = event

        # messages 模式下：模型正在按字输出文本（通常就是用户能看到的聊天文字）
        if mode == "messages":
            msg, metadata = data
            if hasattr(msg, "content") and msg.content:
                # 过滤掉工具调用的隐藏指令，只将普通对话文字抛给控制台
                if msg.type == "AIMessageChunk" or msg.type == "ai":
                    if msg.content and not getattr(msg, "tool_calls", None):
                        full_response += msg.content
                        yield {"type": "token", "content": msg.content}

        # updates 模式下：发生了一些大的阶段跃进，比如模型决定调用工具，或者工具执行出了结果
        elif mode == "updates":
            if isinstance(data, dict):
                for node_name, node_data in data.items():
                    # 侦测到工具刚刚执行完毕
                    if node_name == "tools" and "messages" in node_data:
                        for tool_msg in node_data["messages"]:
                            if hasattr(tool_msg, "name"):
                                yield {
                                    "type": "tool_end",
                                    "tool": tool_msg.name,
                                    "output": str(tool_msg.content)[:2000],
                                }
                    # 侦测到模型发起了一个新的工具调用请求
                    elif node_name == "model" and "messages" in node_data:
                        for agent_msg in node_data["messages"]:
                            if hasattr(agent_msg, "tool_calls") and agent_msg.tool_calls:
                                for tc in agent_msg.tool_calls:
                                    yield {
                                        "type": "tool_start",
                                        "tool": tc["name"],
                                        "input": str(tc.get("args", ""))[:1000],
                                    }

    # 对话彻底结束，统一把拼接好的最后一次总回复发送出去
    yield {"type": "done", "content": full_response}


# ============ 测试代码 ============

if __name__ == "__main__":
    import asyncio

    # 测试 Skills 扫描
    print("=== 测试 Skills 扫描 ===")
    test_skills_dir = Path("./skills")
    if test_skills_dir.exists():
        snapshot = scan_skills(test_skills_dir)
        print(snapshot)
    else:
        print("⚠️ skills/ 目录不存在，跳过扫描测试")

    # 测试 Agent 初始化（需要配置 API Key）
    print("\n=== 测试 Agent 初始化 ===")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        agent = initialize_agent(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            base_dir=Path(".")
        )

        # 测试同步对话
        print("\n=== 测试同步对话 ===")
        response = chat(agent, "你好，请介绍一下你自己")
        print(f"Response: {response}")

        # 测试流式对话
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
