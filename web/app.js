const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const messages = document.querySelector("#messages");
const sendButton = document.querySelector("#sendButton");
const newChatButton = document.querySelector("#newChatButton");
const filesList = document.querySelector("#filesList");
const refreshFilesButton = document.querySelector("#refreshFilesButton");
const fileUploadInput = document.querySelector("#fileUploadInput");

let sessionId = localStorage.getItem("mge-agent-session-id") || crypto.randomUUID();
localStorage.setItem("mge-agent-session-id", sessionId);

function addMessage(role, content, extraClass = "") {
  const item = document.createElement("article");
  item.className = `message ${role} ${extraClass}`.trim();

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "你" : "AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  const body = document.createElement("div");
  body.className = "message-body";
  body.appendChild(bubble);

  item.append(avatar, body);
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function setMessageTrace(item, trace = []) {
  if (!trace.length) return;
  const panel = ensureTracePanel(item);
  panel.list.innerHTML = "";
  trace.forEach((step) => appendTraceStep(item, step));
}

function ensureTracePanel(item) {
  const body = item.querySelector(".message-body");
  let details = body.querySelector(".trace");
  if (!details) {
    details = document.createElement("details");
    details.className = "trace";
    details.open = true;

    const summary = document.createElement("summary");
    summary.textContent = "执行过程（0）";
    details.appendChild(summary);

    const list = document.createElement("div");
    list.className = "trace-list";
    details.appendChild(list);
    body.appendChild(details);
  }

  return {
    details,
    summary: details.querySelector("summary"),
    list: details.querySelector(".trace-list"),
  };
}

function appendTraceStep(item, step) {
  const panel = ensureTracePanel(item);
  const count = panel.list.children.length + 1;
  const title = step.content || step.type || "过程事件";

  const row = document.createElement("div");
  row.className = "trace-row";
  const content = document.createElement("div");
  content.textContent = title;
  row.appendChild(content);

  if (step.detail) {
    const detail = document.createElement("pre");
    detail.textContent = String(step.detail).slice(0, 1200);
    row.appendChild(detail);
  }

  panel.list.appendChild(row);
  panel.summary.textContent = `执行过程（${count}） ${title}`;
  messages.scrollTop = messages.scrollHeight;
}

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
}

async function sendMessage(message) {
  sendButton.disabled = true;
  input.disabled = true;
  const pending = addMessage("assistant", "正在响应...", "typing");
  const bubble = pending.querySelector(".bubble");
  const trace = [];
  let hasToken = false;

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "请求失败");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const lines = part.split("\n");
        const eventLine = lines.find((line) => line.startsWith("event: "));
        const dataLine = lines.find((line) => line.startsWith("data: "));
        if (!eventLine || !dataLine) continue;

        const eventName = eventLine.slice(7).trim();
        const data = JSON.parse(dataLine.slice(6));

        if (eventName === "start") {
          sessionId = data.session_id;
          localStorage.setItem("mge-agent-session-id", sessionId);
        } else if (eventName === "token") {
          if (!hasToken) {
            bubble.textContent = "";
            hasToken = true;
          }
          bubble.textContent += data.content || "";
          messages.scrollTop = messages.scrollHeight;
        } else if (eventName === "trace") {
          trace.push(data);
          appendTraceStep(pending, data);
        } else if (eventName === "done") {
          sessionId = data.session_id;
          localStorage.setItem("mge-agent-session-id", sessionId);
          if (!hasToken && data.response) {
            bubble.textContent = data.response;
          }
        } else if (eventName === "error") {
          throw new Error(data.error || "流式响应失败");
        }
      }
    }

    setMessageTrace(pending, trace);
    pending.classList.remove("typing");
  } catch (error) {
    pending.querySelector(".bubble").textContent = `出错了：${error.message}`;
    pending.classList.remove("typing");
  } finally {
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  addMessage("user", message);
  input.value = "";
  autosize();
  sendMessage(message);
});

input.addEventListener("input", autosize);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

newChatButton.addEventListener("click", () => {
  sessionId = crypto.randomUUID();
  localStorage.setItem("mge-agent-session-id", sessionId);
  messages.innerHTML = "";
  addMessage(
    "assistant",
    "已新建对话。你可以继续询问合金设计流程、数据处理、模型训练与优化任务。"
  );
  input.focus();
});

function formatSize(size) {
  if (size === null || size === undefined) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function loadFiles() {
  filesList.textContent = "加载中...";
  try {
    const response = await fetch("/api/files");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "文件列表获取失败");
    renderFiles(data.files || []);
  } catch (error) {
    filesList.textContent = `出错了：${error.message}`;
  }
}

function renderFiles(files) {
  filesList.innerHTML = "";
  if (!files.length) {
    filesList.textContent = "当前目录为空。";
    return;
  }

  files.forEach((file) => {
    const row = document.createElement("div");
    row.className = `file-row ${file.type}`;

    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = file.type === "directory" ? "DIR" : "FILE";

    const meta = document.createElement("div");
    meta.className = "file-meta";

    const name = document.createElement("div");
    name.className = "file-name";
    name.textContent = file.name;

    const sub = document.createElement("div");
    sub.className = "file-sub";
    sub.textContent = file.type === "directory" ? "目录" : formatSize(file.size);

    meta.append(name, sub);
    row.append(icon, meta);

    if (file.type === "file" && !file.protected) {
      const del = document.createElement("button");
      del.className = "delete-file-button";
      del.type = "button";
      del.title = "删除文件";
      del.setAttribute("aria-label", `删除 ${file.name}`);
      del.textContent = "×";
      del.addEventListener("click", () => deleteFile(file.path));
      row.appendChild(del);
    } else if (file.protected) {
      const lock = document.createElement("span");
      lock.className = "protected-file";
      lock.textContent = "锁";
      row.appendChild(lock);
    }

    filesList.appendChild(row);
  });
}

async function deleteFile(path) {
  if (!confirm(`确定删除 ${path} 吗？`)) return;
  try {
    const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`, {
      method: "DELETE",
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "删除失败");
    renderFiles(data.files || []);
  } catch (error) {
    alert(`删除失败：${error.message}`);
  }
}

async function uploadFile(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });

  const response = await fetch("/api/files/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      content_base64: btoa(binary),
    }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "上传失败");
  renderFiles(data.files || []);
}

refreshFilesButton.addEventListener("click", loadFiles);
fileUploadInput.addEventListener("change", async () => {
  const file = fileUploadInput.files[0];
  if (!file) return;
  try {
    await uploadFile(file);
  } catch (error) {
    alert(`上传失败：${error.message}`);
  } finally {
    fileUploadInput.value = "";
  }
});

autosize();
loadFiles();
