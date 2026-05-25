import asyncio
import base64
import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "web"
SKILLS_DIR = ROOT_DIR / "Skills"
PROTECTED_FILES = {".env"}
HIDDEN_FILE_SUFFIXES = {".py", ".ipynb"}
DEFAULT_AGENT_PYTHON = Path(r"D:\anaconda3\envs\pytorch_gpu\python.exe")
THERMO_KEYWORDS = ("热力学", "热物性", "thermo", "thermo-calc", "thermocalc", "scheil")
THERMO_EXPLICIT_RUN_WORDS = ("执行", "运行", "开始", "启动", "立即", "现在", "直接", "run", "calculate")
THERMO_PREPARE_WORDS = ("准备", "后续", "预处理", "处理", "检查", "读取", "确认", "可以", "能否", "能不能", "可不可以", "吗")

load_dotenv(ROOT_DIR / ".env")

_agent = None
_agent_lock = threading.Lock()
_sessions = {}


def get_agent_python():
    configured = os.getenv("AGENT_PYTHON") or os.getenv("PYTORCH_GPU_PYTHON")
    if configured:
        return str(Path(configured))
    if DEFAULT_AGENT_PYTHON.exists():
        return str(DEFAULT_AGENT_PYTHON)
    return sys.executable


def safe_project_path(raw_path):
    normalized = str(raw_path or "").replace("\\", "/").lstrip("/")
    target = (ROOT_DIR / normalized).resolve()
    if target != ROOT_DIR and ROOT_DIR not in target.parents:
        raise ValueError("Path escapes project root")
    return target


def list_current_files():
    items = []
    for path in sorted(ROOT_DIR.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        if path.name == "__pycache__":
            continue
        if path.is_file() and path.suffix.lower() in HIDDEN_FILE_SUFFIXES:
            continue
        rel_path = path.relative_to(ROOT_DIR).as_posix()
        items.append(
            {
                "name": path.name,
                "path": rel_path,
                "type": "directory" if path.is_dir() else "file",
                "size": path.stat().st_size if path.is_file() else None,
                "modified": int(path.stat().st_mtime),
                "protected": path.name in PROTECTED_FILES,
            }
        )
    return items


async def collect_agent_response(agent, message, history):
    from base_agent import chat_stream

    trace = [{"type": "status", "content": "收到消息，开始处理。"}]
    final_response = ""

    async for event in chat_stream(agent, message, history):
        event_type = event.get("type")
        if event_type == "tool_start":
            trace.append(
                {
                    "type": "tool_start",
                    "content": f"调用工具：{event.get('tool', 'unknown')}",
                    "detail": event.get("input", ""),
                }
            )
        elif event_type == "tool_end":
            trace.append(
                {
                    "type": "tool_end",
                    "content": f"工具完成：{event.get('tool', 'unknown')}",
                    "detail": event.get("output", ""),
                }
            )
        elif event_type == "done":
            final_response = event.get("content", "")

    trace.append({"type": "status", "content": "回复生成完成。"})
    return final_response, trace


def is_thermocalc_run_request(message):
    text = message.lower()
    if "不执行" in message or "没执行" in message or "卡" in message:
        return False
    has_keyword = any(keyword in text for keyword in THERMO_KEYWORDS)
    if not has_keyword:
        return False

    has_explicit_run = any(word in text for word in THERMO_EXPLICIT_RUN_WORDS)
    if not has_explicit_run:
        return False

    is_preparation_or_question = any(word in text for word in THERMO_PREPARE_WORDS)
    force_now = any(word in text for word in ("现在", "立即", "直接", "开始执行", "开始运行"))
    return force_now or not is_preparation_or_question


def choose_thermocalc_workbook():
    composition_files = sorted(
        ROOT_DIR.glob("*composition_only*.xlsx"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if composition_files:
        return composition_files[0]

    candidates = [
        item
        for item in sorted(ROOT_DIR.glob("*.xlsx"), key=lambda path: path.stat().st_mtime, reverse=True)
        if "thermal" not in item.stem.lower()
    ]
    if not candidates:
        raise FileNotFoundError("未找到可用于热力学计算的 .xlsx 工作簿。")
    return candidates[0]


def infer_balance_element(workbook):
    if "in718" in workbook.stem.lower():
        return "Ni"
    return os.getenv("THERMO_BALANCE_ELEMENT", "Ni")


def get_agent():
    global _agent
    if _agent is not None:
        return _agent

    with _agent_lock:
        if _agent is not None:
            return _agent

        from base_agent import initialize_agent

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")

        _agent = initialize_agent(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
            skills_dir=SKILLS_DIR,
            base_dir=ROOT_DIR,
        )
        return _agent


class AgentHandler(SimpleHTTPRequestHandler):
    server_version = "MGEAgentUI/0.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/files":
            self._send_json({"files": list_current_files()})
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/files/upload":
            self._handle_upload()
            return
        if path == "/api/chat/stream":
            self._handle_chat_stream()
            return

        if path != "/api/chat":
            self.send_error(404, "Not found")
            return

        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip()
            session_id = str(payload.get("session_id") or uuid.uuid4())

            if not message:
                self._send_json({"error": "请输入消息。"}, status=400)
                return

            history = _sessions.setdefault(session_id, [])
            trace = [{"type": "status", "content": "准备智能体。"}]
            agent = get_agent()

            response, agent_trace = asyncio.run(collect_agent_response(agent, message, history))
            trace.extend(agent_trace)
            if not response:
                from base_agent import chat

                trace.append({"type": "status", "content": "流式结果为空，切换为完整回复模式。"})
                response = chat(agent, message, history)

            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": response})

            self._send_json(
                {
                    "session_id": session_id,
                    "response": response,
                    "trace": trace,
                    "history_length": len(history),
                }
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/files":
            self.send_error(404, "Not found")
            return

        try:
            query = parse_qs(parsed.query)
            raw_path = query.get("path", [""])[0]
            target = safe_project_path(raw_path)
            if not target.exists():
                self._send_json({"error": "文件不存在。"}, status=404)
                return
            if not target.is_file():
                self._send_json({"error": "当前仅支持删除文件。"}, status=400)
                return
            if target.name in PROTECTED_FILES:
                self._send_json({"error": "该文件受保护，不能从界面删除。"}, status=400)
                return
            target.unlink()
            self._send_json({"ok": True, "files": list_current_files()})
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, event, payload):
        body = (
            f"event: {event}\n"
            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        ).encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _handle_chat_stream(self):
        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip()
            session_id = str(payload.get("session_id") or uuid.uuid4())

            if not message:
                self._send_json({"error": "请输入消息。"}, status=400)
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()

            history = _sessions.setdefault(session_id, [])
            self._send_sse("start", {"session_id": session_id})

            if is_thermocalc_run_request(message):
                response = self._stream_thermocalc_run(message)
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response})
                self._send_sse(
                    "done",
                    {
                        "session_id": session_id,
                        "response": response,
                        "history_length": len(history),
                    },
                )
                return

            self._send_sse("trace", {"type": "status", "content": "准备智能体。"})
            agent = get_agent()

            async def stream_agent():
                from base_agent import chat, chat_stream

                full_response = ""
                done_response = ""
                async for event in chat_stream(agent, message, history):
                    event_type = event.get("type")
                    if event_type == "token":
                        content = event.get("content", "")
                        full_response += content
                        self._send_sse("token", {"content": content})
                    elif event_type == "tool_start":
                        self._send_sse(
                            "trace",
                            {
                                "type": "tool_start",
                                "content": f"调用工具：{event.get('tool', 'unknown')}",
                                "detail": event.get("input", ""),
                            },
                        )
                    elif event_type == "tool_end":
                        self._send_sse(
                            "trace",
                            {
                                "type": "tool_end",
                                "content": f"工具完成：{event.get('tool', 'unknown')}",
                                "detail": event.get("output", ""),
                            },
                        )
                    elif event_type == "done":
                        done_response = event.get("content", "")

                response = done_response or full_response
                if not response:
                    self._send_sse(
                        "trace",
                        {"type": "status", "content": "流式结果为空，切换为完整回复模式。"},
                    )
                    response = chat(agent, message, history)
                    self._send_sse("token", {"content": response})

                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response})
                self._send_sse("trace", {"type": "status", "content": "回复生成完成。"})
                self._send_sse(
                    "done",
                    {
                        "session_id": session_id,
                        "response": response,
                        "history_length": len(history),
                    },
                )

            asyncio.run(stream_agent())
        except Exception as exc:
            try:
                self._send_sse("error", {"error": str(exc)})
            except Exception:
                self._send_json({"error": str(exc)}, status=500)

    def _stream_thermocalc_run(self, message):
        workbook = choose_thermocalc_workbook()
        balance_element = infer_balance_element(workbook)
        output = ROOT_DIR / f"{workbook.stem}_thermal_results.xlsx"
        script = ROOT_DIR / "Skills" / "alloy-thermocalc-evaluate" / "scripts" / "append_thermocalc_results.py"
        command = [
            get_agent_python(),
            str(script),
            str(workbook),
            "--balance-element",
            balance_element,
            "--heartbeat-seconds",
            "10",
            "--output",
            str(output),
        ]

        intro = (
            f"开始执行热力学计算。\n\n"
            f"输入工作簿：{workbook.name}\n"
            f"平衡元素：{balance_element}\n"
            f"输出文件：{output.name}\n\n"
        )
        self._send_sse("token", {"content": intro})
        self._send_sse(
            "trace",
            {
                "type": "tool_start",
                "content": "启动 Thermo-Calc 计算脚本。",
                "detail": " ".join(command),
            },
        )

        process = subprocess.Popen(
            command,
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        recent_lines = []
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.rstrip()
            if not clean:
                continue
            recent_lines.append(clean)
            recent_lines = recent_lines[-12:]
            self._send_sse(
                "trace",
                {
                    "type": "tool_output",
                    "content": "Thermo-Calc 输出",
                    "detail": clean,
                },
            )

        return_code = process.wait()
        if return_code == 0:
            response = f"热力学计算完成，结果已保存到 {output.name}。"
            self._send_sse("token", {"content": response})
            self._send_sse(
                "trace",
                {
                    "type": "tool_end",
                    "content": "Thermo-Calc 计算完成。",
                    "detail": "\n".join(recent_lines),
                },
            )
            return intro + response

        response = f"热力学计算未完成，脚本退出码为 {return_code}。请展开执行过程查看最后的错误信息。"
        self._send_sse("token", {"content": response})
        self._send_sse(
            "trace",
            {
                "type": "tool_end",
                "content": "Thermo-Calc 计算失败。",
                "detail": "\n".join(recent_lines),
            },
        )
        return intro + response

    def _handle_upload(self):
        try:
            payload = self._read_json()
            filename = Path(str(payload.get("filename", ""))).name
            content_base64 = str(payload.get("content_base64", ""))
            if not filename or not content_base64:
                self._send_json({"error": "上传内容不完整。"}, status=400)
                return

            target = safe_project_path(filename)
            if target.exists() and not target.is_file():
                self._send_json({"error": "目标名称已被目录占用。"}, status=400)
                return

            target.write_bytes(base64.b64decode(content_base64))
            self._send_json({"ok": True, "files": list_current_files()})
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)


def run(host="127.0.0.1", port=8000):
    if not STATIC_DIR.exists():
        raise RuntimeError(f"Static directory not found: {STATIC_DIR}")

    server = ThreadingHTTPServer((host, port), AgentHandler)
    print(f"Agent UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("PORT", "8000"))
    run(port=port)
