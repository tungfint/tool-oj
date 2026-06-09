#!/usr/bin/env python3
"""Local web UI for preparing, uploading, and transferring OJ problems."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import uuid
from dataclasses import replace
from pathlib import Path
from urllib.parse import urljoin

from flask import Flask, Response, jsonify, render_template_string, request

from transfer_tinhoctre_to_hncode import (
    ProblemInfo,
    create_hncode_problem,
    destination_problem_exists,
    fetch_source_problem,
    login_hncode,
    upload_hncode_tests,
)
from upload_tinhoctre_batch import (
    GeneratedTests,
    ProblemBundle,
    clean_statement,
    csrf_token,
    discover_bundles,
    extract_zip,
    generate_tests,
    problem_exists as tinhoctre_problem_exists,
    submit_solution,
    upload_tests as upload_tinhoctre_tests,
)


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
DEFAULT_ZIP = r"E:\Google Drive\Google Drive\1-School\4-KiThi\THT\2026\5Tinh\04-06\tht26_5_bai_files.zip"

TARGETS = {
    "hnoj": {
        "label": "HNOJ",
        "base_url": "https://hnoj.edu.vn",
        "type_id": "1",
        "group_id": "1",
        "languages": {"C++17": "4", "Pascal": "7", "Python 3": "9", "Scratch": "12"},
        "default_user": "hncode",
        "test_backend": "dmoj",
    },
    "hncode": {
        "label": "HNCode",
        "base_url": "https://oj.hncode.edu.vn",
        "type_id": "387",
        "group_id": "105",
        "languages": {"C++17": "12", "C++20": "14", "Pascal": "10", "Python 3": "8", "PyPy 3": "16"},
        "default_user": "hncode",
        "test_backend": "dmoj",
    },
    "tinhoctre": {
        "label": "TinHocTre",
        "base_url": "https://tinhoctre.vn",
        "type_id": "1",
        "group_id": "1",
        "languages": {
            "C++17": "",
            "C++20": "",
            "Pascal": "",
            "Python 3": "9",
            "PyPy 3": "17",
            "Scratch": "",
        },
        "default_user": "admin",
        "test_backend": "vnoj",
    },
}

PROMPT_GUIDE = """Với mỗi bài trong danh sách dưới đây, hãy tạo đủ 4 file:

1. File sinh test:
   - Tên file: gentest_<ma_bai>.py
   - Ví dụ: gentest_tht26_tongbi.py

2. File lời giải Python:
   - Tên file: sol_<ma_bai>.py
   - Ví dụ: sol_tht26_tongbi.py

3. File lời giải C++:
   - Tên file: sol_<ma_bai>.cpp
   - Ví dụ: sol_tht26_tongbi.cpp

4. File đề bài Markdown:
   - Tên file: <ma_bai>.md
   - Ví dụ: tht26_tongbi.md
   - Dòng đầu tiên của file phải có đúng cấu trúc:
     Tên bài | Mã bài
   - Ví dụ:
     Tổng bi | tht26_tongbi
   - Sau dòng đầu tiên là toàn bộ nội dung đề bài.

Yêu cầu đối với file sinh test:

- File sinh test là file Python.
- Trong file sinh test phải nhúng lời giải chuẩn bằng C++ để sinh output.
- Khi chạy file sinh test, chương trình tự tạo thư mục test cho bài tương ứng.
- Tên thư mục test nên là mã bài, ví dụ:
  tht26_tongbi/
- Các file test trong thư mục có dạng:
  01.inp, 01.out
  02.inp, 02.out
  ...
- Sau khi sinh test, file sinh test tự nén thư mục test thành:
  tht26_tongbi.zip

Yêu cầu đối với bộ test:

- Bộ test phải đủ mạnh, phủ đủ các trường hợp đặc biệt và trường hợp biên.
- Dữ liệu phải đúng giới hạn của đề bài.
- Nếu đề có subtask, số lượng test phải phân bố đúng theo tỉ lệ subtask.
- Nếu bài đơn giản, chỉ cần khoảng 10 test.
- Nếu bài cần nhiều trường hợp để kiểm tra chặt chẽ hơn, có thể sinh khoảng 20 test hoặc nhiều hơn.
- Cần có 01 test ví dụ, các test nhỏ, test biên, test ngẫu nhiên có kiểm soát, test đủ các trường hợp và test lớn.

Sau khi tạo xong, hãy nén toàn bộ các file đã tạo thành một file zip duy nhất và gửi lại cho tôi.

Ví dụ với bài:

Tổng bi | tht26_tongbi

Cần tạo 4 file:

- gentest_tht26_tongbi.py
- sol_tht26_tongbi.py
- sol_tht26_tongbi.cpp
- tht26_tongbi.md

Hãy thực hiện cho toàn bộ các bài được cung cấp bên dưới."""

app = Flask(__name__)
prepared_uploads: dict[str, dict] = {}
prepared_transfers: dict[str, dict] = {}


class ProblemAlreadyExists(RuntimeError):
    pass


@app.before_request
def require_basic_auth():
    auth_user = os.getenv("TOOL_OJ_AUTH_USER")
    auth_pass = os.getenv("TOOL_OJ_AUTH_PASS")
    if not auth_user and not auth_pass:
        return None
    auth = request.authorization
    if auth and auth.username == auth_user and auth.password == auth_pass:
        return None
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Tool HNCode"'},
    )


PAGE = r"""
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tool HNCode</title>
  <link rel="icon" type="image/svg+xml" href="/static/favicon-HNCode.svg">
  <style>
    :root { --bg:#f5f7fb; --panel:#fff; --ink:#172033; --muted:#667085; --line:#d8dee9; --soft:#eef2f6; --accent:#0f766e; --ok:#087443; --bad:#b42318; --code:#101828; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI", Arial, sans-serif; font-size:14px; }
    header { background:var(--panel); border-bottom:1px solid var(--line); padding:16px 22px; display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
    h1 { margin:0; font-size:22px; letter-spacing:0; }
    h2 { margin:0 0 8px; font-size:18px; }
    h3 { margin:16px 0 8px; font-size:15px; }
    p { color:var(--muted); line-height:1.45; margin:0 0 12px; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; }
    .nav button, button.action { border:1px solid #b8c2d3; border-radius:6px; padding:10px 14px; background:#fff; color:var(--ink); font:inherit; font-weight:700; cursor:pointer; box-shadow:0 1px 2px rgba(16,24,40,.08); }
    .nav button:hover, button.action:hover { border-color:#8fa1b8; background:#f8fafc; }
    .nav button.active, button.primary { background:var(--accent); border-color:var(--accent); color:#fff; box-shadow:0 2px 6px rgba(15,118,110,.24); }
    button.primary:hover { background:#0b665f; border-color:#0b665f; }
    button:disabled { opacity:.5; cursor:not-allowed; }
    main { max-width:1320px; margin:0 auto; padding:20px; display:grid; grid-template-columns:minmax(520px, 1.1fr) minmax(360px, .9fr); gap:18px; }
    section { background:var(--panel); border:1px solid var(--line); border-radius:8px; }
    .panel { display:none; padding:18px; }
    .panel.active { display:block; }
    label { display:block; margin:12px 0 6px; color:#344054; font-weight:650; }
    input[type=text], input[type=password], select, textarea { width:100%; border:1px solid var(--line); border-radius:6px; padding:9px 10px; font:inherit; background:#fff; color:var(--ink); }
    textarea { min-height:78px; resize:vertical; line-height:1.45; }
    .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .grid-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
    .row { display:flex; gap:10px; align-items:end; flex-wrap:wrap; }
    .row > .grow { flex:1 1 340px; }
    .actions { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
    #toggleGuide { margin-top:6px; }
    .table-tools { display:flex; gap:8px; margin-top:14px; flex-wrap:wrap; }
    .note, .guide { border:1px solid #b8d8d3; background:#f0fdfa; color:#134e48; border-radius:8px; padding:12px; line-height:1.48; margin:12px 0; }
    .guide { border-color:var(--line); background:#fafbfc; color:var(--ink); }
    .sample, pre#log { background:var(--code); color:#f2f4f7; border-radius:6px; padding:12px; white-space:pre-wrap; overflow:auto; font-family:Consolas, "Cascadia Mono", monospace; font-size:12px; line-height:1.45; }
    .log-panel { display:grid; grid-template-rows:auto minmax(560px, 1fr); min-height:700px; }
    .log-head { padding:14px 16px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:12px; align-items:center; }
    pre#log { margin:0; border-radius:0 0 8px 8px; }
    .status { border-radius:999px; padding:4px 10px; background:var(--soft); color:var(--muted); font-weight:650; font-size:12px; }
    .status.ok { background:#dcfae6; color:var(--ok); }
    .status.err { background:#fee4e2; color:var(--bad); }
    table { width:100%; border-collapse:collapse; margin-top:14px; font-size:13px; }
    th, td { border-bottom:1px solid var(--line); padding:8px; vertical-align:top; text-align:left; }
    th { background:#f8fafc; font-weight:700; }
    td input[type=text] { padding:6px 7px; }
    a.problem-link { color:var(--accent); font-weight:700; text-decoration:none; }
    .test-meta { color:var(--muted); font-size:12px; line-height:1.4; }
    .lang-list { display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:8px; margin-top:8px; }
    .check { display:flex; align-items:center; gap:7px; }
    .hidden { display:none; }
    @media (max-width:980px) { main { grid-template-columns:1fr; padding:14px; } .grid-2,.grid-3,.lang-list { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Tool HNCode</h1>
    <div class="nav">
      <button type="button" class="active" data-panel="accounts">Tài khoản & Hướng dẫn</button>
      <button type="button" data-panel="upload">Up bài</button>
      <button type="button" data-panel="transfer">Chuyển bài</button>
    </div>
  </header>

  <main>
    <section>
      <div class="panel active" id="panel-accounts">
        <h2>Tài khoản & Hướng dẫn</h2>
        <p>Lưu tạm tài khoản trên trình duyệt máy này. Khi chạy tác vụ, form sẽ tự điền các thông tin đã lưu.</p>
        <div class="grid-3">
          <div><label>HNOJ user</label><input id="acct_hnoj_user" type="text" value="hncode"></div>
          <div><label>HNCode user</label><input id="acct_hncode_user" type="text" value="hncode"></div>
          <div><label>TinHocTre user</label><input id="acct_tinhoctre_user" type="text" value="admin"></div>
        </div>
        <div class="grid-3">
          <div><label>HNOJ password</label><input id="acct_hnoj_pass" type="password"></div>
          <div><label>HNCode password</label><input id="acct_hncode_pass" type="password"></div>
          <div><label>TinHocTre password</label><input id="acct_tinhoctre_pass" type="password"></div>
        </div>
        <div class="actions">
          <button class="action primary" type="button" id="saveAccounts">Lưu tạm</button>
          <button class="action" type="button" id="clearAccounts">Xóa thông tin đã lưu</button>
        </div>
        <button class="action" type="button" id="toggleGuide">Ẩn / Hiện hướng dẫn prompt</button>
        <div class="guide hidden" id="promptGuide"><div class="sample">{{ prompt_guide }}</div></div>
      </div>

      <div class="panel" id="panel-upload">
        <h2>Up bài</h2>
        <p>Chọn web đích, chọn zip bộ bài, bấm Chuẩn bị dữ liệu để xem bảng bài trước khi up thật.</p>
        <div class="grid-2">
          <div>
            <label>Web đích</label>
            <select id="uploadTarget">
              <option value="hnoj">HNOJ</option>
              <option value="hncode">HNCode</option>
              <option value="tinhoctre">TinHocTre</option>
            </select>
          </div>
          <div>
            <label>File zip bộ bài</label>
            <div class="row">
              <div class="grow"><input id="uploadZip" type="text" value="{{ default_zip }}"></div>
              <button class="action" type="button" id="chooseZip">Chọn file</button>
              <input id="zipFileInput" class="hidden" type="file" accept=".zip,application/zip">
            </div>
          </div>
        </div>
        <div class="grid-2">
          <div><label>Giới hạn thời gian</label><input id="timeLimit" type="text" value="1.0"></div>
          <div><label>Giới hạn bộ nhớ</label><input id="memoryLimit" type="text" value="1048576"></div>
        </div>
        <h3>Ngôn ngữ cho phép</h3>
        <div id="languages" class="lang-list"></div>

        <div class="actions">
          <button class="action" type="button" id="toggleAdvanced">Mở rộng thông tin khác</button>
        </div>
        <div id="advancedUpload" class="hidden">
          <div class="grid-3">
            <div><label>Người tạo (Creators)</label><input id="creator" type="text" value="mrtee"></div>
            <div><label>Dạng đề (Problem types)</label><input id="typeLabel" type="text" value="Chưa phân loại" disabled></div>
            <div><label>Nhóm bài (Problem group)</label><input id="groupLabel" type="text" value="Chưa phân loại" disabled></div>
          </div>
        </div>

        <div class="grid-3" style="margin-top:12px">
          <label class="check"><input type="checkbox" id="submitCpp"> Nộp bài chấm thử C++</label>
          <label class="check"><input type="checkbox" id="submitPython" checked> Nộp bài chấm thử Python</label>
          <label class="check"><input type="checkbox" id="noSubmit"> Không nộp bài chấm thử</label>
        </div>
        <div class="actions">
          <button class="action primary" type="button" id="prepareUpload">Chuẩn bị dữ liệu</button>
          <button class="action primary" type="button" id="confirmUpload" disabled>Xác nhận Up bài</button>
        </div>
        <div id="uploadTable"></div>
      </div>

      <div class="panel" id="panel-transfer">
        <h2>Chuyển bài</h2>
        <p>Chọn nguồn, đích và danh sách mã bài. Tool sẽ lấy đề/test từ nguồn rồi tạo bài và upload test ở đích.</p>
        <div class="grid-2">
          <div><label>Nguồn</label><select id="transferSource"><option value="tinhoctre">TinHocTre</option><option value="hnoj">HNOJ</option><option value="hncode">HNCode</option></select></div>
          <div><label>Đích</label><select id="transferDest"><option value="hncode">HNCode</option><option value="hnoj">HNOJ</option><option value="tinhoctre">TinHocTre</option></select></div>
        </div>
        <div class="grid-2">
          <div><label>Giới hạn thời gian mặc định</label><input id="transferTimeLimit" type="text" value="1.0"></div>
          <div><label>Giới hạn bộ nhớ mặc định</label><input id="transferMemoryLimit" type="text" value="1048576"></div>
        </div>
        <div class="actions">
          <button class="action" type="button" id="applyTransferLimits">Áp dụng cho tất cả các bài</button>
          <button class="action" type="button" id="resetTransferLimits">Mặc định</button>
        </div>
        <h3>Ngôn ngữ cho phép ở đích</h3>
        <div id="transferLanguages" class="lang-list"></div>
        <div class="actions">
          <button class="action" type="button" id="toggleTransferAdvanced">Mở rộng thông tin khác</button>
        </div>
        <div id="advancedTransfer" class="hidden">
          <div class="grid-3">
            <div><label>Người tạo (Creators)</label><input id="transferCreator" type="text" value="mrtee"></div>
            <div><label>Dạng đề (Problem types)</label><input id="transferTypeLabel" type="text" value="Chưa phân loại" disabled></div>
            <div><label>Nhóm bài (Problem group)</label><input id="transferGroupLabel" type="text" value="Chưa phân loại" disabled></div>
          </div>
        </div>
        <label>Danh sách mã bài cần chuyển</label>
        <textarea id="transferCodes" placeholder="tht26_tongbi&#10;tht26_quatang"></textarea>
        <div class="actions">
          <button class="action primary" type="button" id="prepareTransfer">Chuẩn bị dữ liệu</button>
          <button class="action primary" type="button" id="confirmTransfer" disabled>Xác nhận chuyển bài</button>
        </div>
        <div id="transferTable"></div>
      </div>
    </section>

    <section class="log-panel">
      <div class="log-head"><h2>Thông tin trả về</h2><span id="jobStatus" class="status">idle</span></div>
      <pre id="log">Sẵn sàng.</pre>
    </section>
  </main>

<script>
const TARGETS = {{ targets_json | safe }};
let preparedUpload = null;
let preparedTransfer = null;
let selectedZipFile = null;

const logEl = document.getElementById("log");
const statusEl = document.getElementById("jobStatus");
function log(text) { logEl.textContent = text; logEl.scrollTop = logEl.scrollHeight; }
function append(text) { logEl.textContent += "\n" + text; logEl.scrollTop = logEl.scrollHeight; }
function status(text, cls="") { statusEl.textContent = text; statusEl.className = "status " + cls; }

for (const button of document.querySelectorAll(".nav button")) {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav button").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    document.getElementById("panel-" + button.dataset.panel).classList.add("active");
  });
}

const accountFields = {
  hnoj_user: document.getElementById("acct_hnoj_user"),
  hnoj_pass: document.getElementById("acct_hnoj_pass"),
  hncode_user: document.getElementById("acct_hncode_user"),
  hncode_pass: document.getElementById("acct_hncode_pass"),
  tinhoctre_user: document.getElementById("acct_tinhoctre_user"),
  tinhoctre_pass: document.getElementById("acct_tinhoctre_pass"),
};
function loadAccounts() {
  for (const [key, input] of Object.entries(accountFields)) {
    const value = localStorage.getItem("chuyenbai." + key);
    if (value !== null) input.value = value;
  }
}
function saveAccounts() {
  for (const [key, input] of Object.entries(accountFields)) localStorage.setItem("chuyenbai." + key, input.value);
}
loadAccounts();
document.getElementById("saveAccounts").onclick = () => { saveAccounts(); append("Đã lưu tạm tài khoản."); };
document.getElementById("clearAccounts").onclick = () => {
  for (const key of Object.keys(accountFields)) localStorage.removeItem("chuyenbai." + key);
  for (const [key, input] of Object.entries(accountFields)) if (key.endsWith("_pass")) input.value = "";
  append("Đã xóa thông tin đã lưu.");
};
document.getElementById("toggleGuide").onclick = () => document.getElementById("promptGuide").classList.toggle("hidden");
document.getElementById("toggleAdvanced").onclick = () => {
  const box = document.getElementById("advancedUpload");
  box.classList.toggle("hidden");
  document.getElementById("toggleAdvanced").textContent = box.classList.contains("hidden") ? "Mở rộng thông tin khác" : "Thu gọn thông tin khác";
};
document.getElementById("toggleTransferAdvanced").onclick = () => {
  const box = document.getElementById("advancedTransfer");
  box.classList.toggle("hidden");
  document.getElementById("toggleTransferAdvanced").textContent = box.classList.contains("hidden") ? "Mở rộng thông tin khác" : "Thu gọn thông tin khác";
};
document.getElementById("applyTransferLimits").onclick = () => {
  const timeLimit = document.getElementById("transferTimeLimit").value;
  const memoryLimit = document.getElementById("transferMemoryLimit").value;
  for (const tr of document.querySelectorAll("#transferTable tbody tr")) {
    const timeInput = tr.querySelector(".row-time");
    const memoryInput = tr.querySelector(".row-memory");
    if (timeInput) timeInput.value = timeLimit;
    if (memoryInput) memoryInput.value = memoryLimit;
  }
  append("Đã áp dụng time/memory mặc định cho tất cả bài trong bảng chuyển.");
};
document.getElementById("resetTransferLimits").onclick = () => {
  for (const tr of document.querySelectorAll("#transferTable tbody tr")) {
    const timeInput = tr.querySelector(".row-time");
    const memoryInput = tr.querySelector(".row-memory");
    if (timeInput) timeInput.value = tr.dataset.sourceTime || "1.0";
    if (memoryInput) memoryInput.value = tr.dataset.sourceMemory || "1048576";
  }
  append("Đã trả time/memory về thông số lấy từ nguồn.");
};
document.getElementById("chooseZip").onclick = () => document.getElementById("zipFileInput").click();
document.getElementById("zipFileInput").onchange = event => {
  selectedZipFile = event.target.files[0] || null;
  if (selectedZipFile) document.getElementById("uploadZip").value = selectedZipFile.name;
};

function renderLanguages() {
  const target = document.getElementById("uploadTarget").value;
  const langs = TARGETS[target].languages;
  document.getElementById("languages").innerHTML = Object.keys(langs).map(name =>
    `<label class="check"><input type="checkbox" value="${name}" checked> ${name}</label>`
  ).join("");
}
function renderTransferLanguages() {
  const target = document.getElementById("transferDest").value;
  const langs = TARGETS[target].languages;
  document.getElementById("transferLanguages").innerHTML = Object.keys(langs).map(name =>
    `<label class="check"><input type="checkbox" value="${name}" checked> ${name}</label>`
  ).join("");
}
document.getElementById("uploadTarget").addEventListener("change", renderLanguages);
document.getElementById("transferDest").addEventListener("change", renderTransferLanguages);
renderLanguages();
renderTransferLanguages();

function selectedLanguages() {
  return [...document.querySelectorAll("#languages input:checked")].map(item => item.value);
}
function selectedTransferLanguages() {
  return [...document.querySelectorAll("#transferLanguages input:checked")].map(item => item.value);
}
function accountPayload(target) {
  return {
    username: accountFields[target + "_user"].value,
    password: accountFields[target + "_pass"].value,
  };
}
function uploadSettings() {
  const target = document.getElementById("uploadTarget").value;
  return {
    target,
    zip_path: selectedZipFile ? "" : document.getElementById("uploadZip").value,
    creator: document.getElementById("creator").value,
    time_limit: document.getElementById("timeLimit").value,
    memory_limit: document.getElementById("memoryLimit").value,
    languages: selectedLanguages(),
    no_submit: document.getElementById("noSubmit").checked,
    submit_cpp: document.getElementById("submitCpp").checked,
    submit_python: document.getElementById("submitPython").checked,
    ...accountPayload(target),
  };
}
function transferSettings() {
  const dest = document.getElementById("transferDest").value;
  return {
    creator: document.getElementById("transferCreator").value,
    time_limit: document.getElementById("transferTimeLimit").value,
    memory_limit: document.getElementById("transferMemoryLimit").value,
    languages: selectedTransferLanguages(),
    ...accountPayload(dest),
  };
}
async function postJson(url, payload) {
  const res = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function prepareUploadRequest(settings) {
  if (!selectedZipFile) return postJson("/api/prepare-upload", settings);
  const form = new FormData();
  form.append("zip_file", selectedZipFile);
  form.append("payload", JSON.stringify(settings));
  const res = await fetch("/api/prepare-upload", {method:"POST", body:form});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

document.getElementById("prepareUpload").onclick = async () => {
  try {
    status("running");
    log("Đang chuẩn bị dữ liệu...");
    const data = await prepareUploadRequest(uploadSettings());
    preparedUpload = data.prepare_id;
    renderUploadTable(data.rows);
    document.getElementById("confirmUpload").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

function renderUploadTable(rows) {
  document.getElementById("uploadTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#uploadTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#uploadTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Up đề</th><th>Up test</th><th>File test</th><th>Số test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_code)}" data-source-time="${escapeHtml(row.source_time_limit || row.time_limit || "1.0")}" data-source-memory="${escapeHtml(row.source_memory_limit || row.memory_limit || "1048576")}">
      <td><input type="checkbox" class="row-selected" checked></td>
      <td><input type="text" class="row-code" value="${escapeHtml(row.code)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name)}"></td>
      <td><input type="checkbox" class="row-statement" checked></td>
      <td><input type="checkbox" class="row-tests" checked></td>
      <td><div class="test-meta">${escapeHtml(row.test_file)}</div></td>
      <td>${row.test_count}</td>
      <td class="row-status">Chưa up</td>
    </tr>`).join("")}</tbody></table>`;
}
function collectUploadRows() {
  return [...document.querySelectorAll("#uploadTable tbody tr")].map(tr => ({
    original_code: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    code: tr.querySelector(".row-code").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    upload_statement: tr.querySelector(".row-statement").checked,
    upload_tests: tr.querySelector(".row-tests").checked,
  }));
}
document.getElementById("confirmUpload").onclick = async () => {
  try {
    status("running");
    log("Đang up bài...");
    const data = await postJson("/api/confirm-upload", {prepare_id: preparedUpload, settings: uploadSettings(), rows: collectUploadRows()});
    applyStatuses(data.rows, "#uploadTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareTransfer").onclick = async () => {
  try {
    status("running");
    log("Đang đọc dữ liệu bài nguồn...");
    const source = document.getElementById("transferSource").value;
    const dest = document.getElementById("transferDest").value;
    const codes = document.getElementById("transferCodes").value.split(/[\s,]+/).filter(Boolean);
    const data = await postJson("/api/prepare-transfer", {
      source, dest, codes,
      source_account: accountPayload(source),
      settings: transferSettings(),
    });
    preparedTransfer = data.prepare_id;
    renderTransferTable(data.rows);
    document.getElementById("confirmTransfer").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
function renderTransferTable(rows) {
  document.getElementById("transferTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#transferTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#transferTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Time</th><th>Memory</th><th>Up đề</th><th>Up test</th><th>Bộ test</th><th>Số test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_code)}">
      <td><input type="checkbox" class="row-selected" checked></td>
      <td><input type="text" class="row-code" value="${escapeHtml(row.code)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name || "")}"></td>
      <td><input type="text" class="row-time" value="${escapeHtml(row.time_limit || "1.0")}"></td>
      <td><input type="text" class="row-memory" value="${escapeHtml(row.memory_limit || "1048576")}"></td>
      <td><input type="checkbox" class="row-statement" checked></td>
      <td><input type="checkbox" class="row-tests" checked></td>
      <td>${row.test_link ? `<a class="problem-link" href="${escapeHtml(row.test_link)}" target="_blank" rel="noopener">Bộ test</a>` : escapeHtml(row.test_file)}</td><td>${row.test_count}</td><td class="row-status">${escapeHtml(row.status)}</td>
    </tr>`).join("")}</tbody></table>`;
}
document.getElementById("confirmTransfer").onclick = async () => {
  try {
    status("running");
    log("Đang chuyển bài...");
    const source = document.getElementById("transferSource").value;
    const dest = document.getElementById("transferDest").value;
    const data = await postJson("/api/confirm-transfer", {
      prepare_id: preparedTransfer,
      source, dest, rows: collectRows("#transferTable"),
      settings: transferSettings(),
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
    });
    applyStatuses(data.rows, "#transferTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
function collectRows(selector) {
  return [...document.querySelectorAll(selector + " tbody tr")].map(tr => ({
    original_code: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    code: tr.querySelector(".row-code").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    time_limit: tr.querySelector(".row-time") ? tr.querySelector(".row-time").value.trim() : "",
    memory_limit: tr.querySelector(".row-memory") ? tr.querySelector(".row-memory").value.trim() : "",
    upload_statement: tr.querySelector(".row-statement").checked,
    upload_tests: tr.querySelector(".row-tests").checked,
  }));
}
function setRowSelection(selector, checked) {
  document.querySelectorAll(selector + " .row-selected").forEach(item => { item.checked = checked; });
}
function applyStatuses(rows, selector) {
  const byOriginal = new Map(rows.map(row => [row.original_code, row]));
  for (const tr of document.querySelectorAll(selector + " tbody tr")) {
    const row = byOriginal.get(tr.dataset.original);
    if (!row) continue;
    const link = row.link ? ` <a class="problem-link" href="${escapeHtml(row.link)}" target="_blank" rel="noopener">Link</a>` : "";
    tr.querySelector(".row-status").innerHTML = `${escapeHtml(row.status)}${link}`;
  }
}
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[ch]));
}
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(
        PAGE,
        default_zip=DEFAULT_ZIP,
        prompt_guide=PROMPT_GUIDE,
        targets_json=json.dumps(TARGETS, ensure_ascii=False),
    )


@app.post("/api/prepare-upload")
def api_prepare_upload():
    try:
        payload = upload_payload()
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / prepare_id
        source_dir = root / "source"
        build_root = root / "generated"
        root.mkdir(parents=True, exist_ok=True)
        zip_path = receive_zip_file(root, payload)
        extract_zip(zip_path, source_dir)
        build_root.mkdir(parents=True, exist_ok=True)

        bundles = discover_bundles(source_dir)
        tests: dict[str, GeneratedTests] = {}
        rows = []
        log_lines = [f"Đã đọc {len(bundles)} bài từ {zip_path.name}."]
        for bundle in bundles:
            generated = generate_tests(bundle, build_root)
            tests[bundle.code] = generated
            rows.append(
                {
                    "original_code": bundle.code,
                    "code": bundle.code,
                    "name": bundle.name,
                    "test_file": generated.zip_path.name,
                    "test_count": len(generated.input_files),
                }
            )
            source = "gentest" if bundle.generator else "zip có sẵn"
            log_lines.append(f"- {bundle.code}: {bundle.name}, {len(generated.input_files)} test, nguồn {source}.")
        prepared_uploads[prepare_id] = {"root": root, "bundles": {b.code: b for b in bundles}, "tests": tests}
        return jsonify({"prepare_id": prepare_id, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


def upload_payload() -> dict:
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        raw = request.form.get("payload", "{}")
        return json.loads(raw)
    return request.get_json(force=True)


def receive_zip_file(root: Path, payload: dict) -> Path:
    uploaded = request.files.get("zip_file")
    if uploaded:
        zip_path = root / "uploaded_package.zip"
        uploaded.save(zip_path)
        return zip_path
    zip_path = Path(payload["zip_path"])
    if not zip_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file zip: {zip_path}")
    return zip_path


@app.post("/api/confirm-upload")
def api_confirm_upload():
    payload = request.get_json(force=True)
    try:
        state = prepared_uploads[payload["prepare_id"]]
        target = payload["settings"]["target"]
        result_rows, log_lines = upload_rows(target, payload["settings"], payload["rows"], state)
        ok = all((not row.get("selected")) or row["status"].startswith("✓") for row in result_rows)
        return jsonify({"ok": ok, "rows": result_rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


def upload_rows(target: str, settings: dict, rows: list[dict], state: dict) -> tuple[list[dict], list[str]]:
    target_info = TARGETS[target]
    log_lines = [f"Đích: {target_info['label']}", "Tạo bài qua admin form: /admin/judge/problem/add/"]
    selected_language_ids = language_ids_for_target(target, settings.get("languages", []))
    if not selected_language_ids:
        log_lines.append("Ngôn ngữ cho phép: form/admin hiện tại không có ID tương ứng, backend bỏ qua an toàn.")
    if settings.get("creator"):
        log_lines.append("Creators được hiển thị trên giao diện; backend chỉ set nếu form admin hỗ trợ trực tiếp.")

    session = login_hncode(target_info["base_url"], settings["username"], settings["password"])
    result_rows = []
    for row in rows:
        row = dict(row)
        if not row.get("selected"):
            row["status"] = "Bỏ qua"
            result_rows.append(row)
            continue
        try:
            bundle = replace(state["bundles"][row["original_code"]], code=row["code"], name=row["name"])
            tests = state["tests"][row["original_code"]]
            upload_one_problem(session, target, target_info, bundle, tests, row, settings, selected_language_ids, log_lines)
            row["status"] = "✓ Thành công"
            row["link"] = problem_url(target_info["base_url"], bundle.code)
        except ProblemAlreadyExists as exc:
            row["status"] = "✗ Bài đã tồn tại"
            log_lines.append(f"✗ {row.get('code')}: {exc}. Bỏ qua bài này và tiếp tục các bài khác.")
        except Exception as exc:
            row["status"] = "✗ Lỗi"
            log_lines.append(f"✗ {row.get('code')}: {exc}")
        result_rows.append(row)
    return result_rows, log_lines


def upload_one_problem(
    session,
    target: str,
    target_info: dict,
    bundle: ProblemBundle,
    tests: GeneratedTests,
    row: dict,
    settings: dict,
    language_ids: list[str],
    log_lines: list[str],
) -> None:
    base_url = target_info["base_url"]
    exists = problem_exists_for_target(session, target, base_url, bundle.code)
    if exists:
        raise ProblemAlreadyExists(f"Mã bài {bundle.code} đã tồn tại tại {problem_url(base_url, bundle.code)}")
    if row.get("upload_statement"):
        info = ProblemInfo(
            code=bundle.code,
            name=bundle.name,
            description=statement_for_target(target, bundle.statement.read_text(encoding="utf-8", errors="replace")),
            points="100",
            partial=True,
            time_limit=settings.get("time_limit") or "1.0",
            memory_limit=settings.get("memory_limit") or "1048576",
            memory_unit="KB",
        )
        change_url = create_hncode_problem(
            session,
            base_url,
            info,
            dest_code=bundle.code,
            type_id=target_info["type_id"],
            group_id=target_info["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{bundle.code}: đã tạo đề qua admin form ({change_url}).")
    else:
        log_lines.append(f"{bundle.code}: không upload đề.")

    if row.get("upload_tests"):
        upload_tests_for_target(session, target, base_url, bundle.code, tests)
        log_lines.append(f"{bundle.code}: đã upload {len(tests.input_files)} test.")
    else:
        log_lines.append(f"{bundle.code}: không upload test.")

    submit_if_requested(session, base_url, bundle, settings, log_lines)


def problem_exists_for_target(session, target: str, base_url: str, code: str) -> bool:
    if target == "tinhoctre":
        return tinhoctre_problem_exists(session, base_url, code)
    return destination_problem_exists(session, base_url, code)


def statement_for_target(target: str, statement: str) -> str:
    text = clean_statement(statement)
    if target == "hncode":
        return text.replace("~", "$")
    return text.replace("$", "~")


def problem_info_for_target(info: ProblemInfo, target: str) -> ProblemInfo:
    return replace(info, description=statement_for_target(target, info.description))


def upload_tests_for_target(session, target: str, base_url: str, code: str, tests: GeneratedTests) -> None:
    if TARGETS[target]["test_backend"] == "vnoj":
        upload_tinhoctre_tests(session, base_url, code, tests)
        return
    from upload_hncode_batch import test_cases_from_files

    upload_hncode_tests(session, base_url, code, tests.zip_path, test_cases_from_files(tests.input_files, tests.output_files))


def submit_if_requested(session, base_url: str, bundle: ProblemBundle, settings: dict, log_lines: list[str]) -> None:
    if settings.get("no_submit"):
        log_lines.append(f"{bundle.code}: không nộp bài chấm thử theo lựa chọn.")
        return
    if settings.get("submit_cpp"):
        if bundle.solution_cpp:
            try:
                submission = submit_solution_file(
                    session,
                    base_url,
                    bundle.code,
                    bundle.solution_cpp,
                    ["C++17", "GNU C++17", "C++20", "GNU C++20", "C++"],
                )
                log_lines.append(f"{bundle.code}: đã nộp thử C++ {submission}.")
            except Exception as exc:
                log_lines.append(f"{bundle.code}: không nộp thử C++ được: {exc}")
        else:
            log_lines.append(f"{bundle.code}: không có sol C++, bỏ qua nộp thử C++.")
    if settings.get("submit_python"):
        if bundle.solution:
            try:
                submission = submit_solution_file(
                    session,
                    base_url,
                    bundle.code,
                    bundle.solution,
                    ["PyPy 3", "Pypy 3", "Python 3", "Python3", "Python"],
                )
                log_lines.append(f"{bundle.code}: đã nộp thử Python {submission}.")
            except Exception:
                try:
                    submission = submit_solution(session, base_url, bundle, language_id="17", poll_seconds=0)
                    log_lines.append(f"{bundle.code}: đã nộp thử Python {submission}.")
                except Exception as exc:
                    log_lines.append(f"{bundle.code}: không nộp thử Python được: {exc}")
        else:
            log_lines.append(f"{bundle.code}: không có sol Python, bỏ qua nộp thử Python.")


def submit_solution_file(session, base_url: str, code: str, source_path: Path, preferred_languages: list[str]) -> str:
    submit_url = urljoin(base_url, f"/problem/{code}/submit")
    page = session.get(submit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Submit page failed: HTTP {page.status_code}")
    language_id = language_id_from_submit_page(page.text, preferred_languages)
    if not language_id:
        raise RuntimeError("không tìm thấy ngôn ngữ phù hợp trên trang submit")
    result = session.post(
        submit_url,
        data={
            "csrfmiddlewaretoken": csrf_token(page.text),
            "source": source_path.read_text(encoding="utf-8", errors="replace"),
            "language": language_id,
            "judge": "",
        },
        headers={"Referer": submit_url},
        allow_redirects=True,
        timeout=30,
    )
    if not result.ok:
        raise RuntimeError(f"Submit failed: HTTP {result.status_code}")
    return result.url


def language_id_from_submit_page(page: str, preferred_languages: list[str]) -> str:
    select_match = re.search(r"<select\b[^>]*name=[\"']language[\"'][^>]*>(.*?)</select>", page, re.S | re.I)
    haystack = select_match.group(1) if select_match else page
    options: list[tuple[str, str]] = []
    for match in re.finditer(r"<option\b([^>]*)>(.*?)</option>", haystack, re.S | re.I):
        attrs, label_html = match.groups()
        value_match = re.search(r"value=[\"']([^\"']+)", attrs)
        if not value_match:
            continue
        label = html.unescape(re.sub(r"<.*?>", " ", label_html)).strip()
        options.append((html.unescape(value_match.group(1)), label))
    for preferred in preferred_languages:
        wanted = normalize_language_label(preferred)
        for value, label in options:
            if wanted and wanted in normalize_language_label(label):
                return value
    return ""


def normalize_language_label(label: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", label.lower())


def language_ids_for_target(target: str, names: list[str]) -> list[str]:
    mapping = TARGETS[target]["languages"]
    return [mapping[name] for name in names if mapping.get(name)]


def problem_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}")


def test_data_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}/test_data")


@app.post("/api/prepare-transfer")
def api_prepare_transfer():
    payload = request.get_json(force=True)
    source = payload["source"]
    dest = payload["dest"]
    codes = [code.strip() for code in payload.get("codes", []) if code.strip()]
    if not codes:
        return jsonify({"error": "Chưa nhập mã bài cần chuyển."}), 400
    if source == dest:
        return jsonify({"error": "Nguồn và đích đang trùng nhau."}), 400
    try:
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / ("transfer_" + prepare_id)
        root.mkdir(parents=True, exist_ok=True)
        source_account = payload["source_account"]
        src = login_hncode(TARGETS[source]["base_url"], source_account["username"], source_account["password"])
        rows = []
        state_items = {}
        log_lines = [f"Đọc dữ liệu nguồn: {TARGETS[source]['label']} → {TARGETS[dest]['label']}"]
        for code in codes:
            try:
                info, zip_path, cases, zip_url = fetch_source_problem(src, TARGETS[source]["base_url"], code, root)
                state_items[code] = {"info": info, "zip_path": zip_path, "cases": cases, "zip_url": zip_url}
                rows.append(
                    {
                        "original_code": code,
                        "code": info.code or code,
                        "name": info.name,
                        "time_limit": info.time_limit or payload.get("settings", {}).get("time_limit") or "1.0",
                        "memory_limit": info.memory_limit or payload.get("settings", {}).get("memory_limit") or "1048576",
                        "source_time_limit": info.time_limit or "1.0",
                        "source_memory_limit": info.memory_limit or "1048576",
                        "test_file": zip_path.name,
                        "test_link": test_data_url(TARGETS[source]["base_url"], code),
                        "test_count": len(cases),
                        "status": "Đã đọc",
                    }
                )
                log_lines.append(f"- {code}: {info.name}, {len(cases)} test, bộ test {test_data_url(TARGETS[source]['base_url'], code)}")
            except Exception as exc:
                rows.append(
                    {
                        "original_code": code,
                        "code": code,
                        "name": "",
                        "time_limit": payload.get("settings", {}).get("time_limit") or "1.0",
                        "memory_limit": payload.get("settings", {}).get("memory_limit") or "1048576",
                        "source_time_limit": "1.0",
                        "source_memory_limit": "1048576",
                        "test_file": "Lỗi khi đọc nguồn",
                        "test_link": test_data_url(TARGETS[source]["base_url"], code),
                        "test_count": 0,
                        "status": "✗ Lỗi đọc nguồn",
                    }
                )
                log_lines.append(f"✗ {code}: {exc}")
        prepared_transfers[prepare_id] = {"root": root, "source": source, "dest": dest, "items": state_items}
        return jsonify({"prepare_id": prepare_id, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/confirm-transfer")
def api_confirm_transfer():
    payload = request.get_json(force=True)
    rows = payload["rows"]
    source = payload["source"]
    dest = payload["dest"]
    settings = payload.get("settings", {})
    log_lines = [
        f"Chuyển bài: {TARGETS[source]['label']} → {TARGETS[dest]['label']}",
        "Tạo bài đích qua admin form: /admin/judge/problem/add/",
    ]
    result_rows = []
    if source == dest:
        for row in rows:
            row["status"] = "✗ Nguồn và đích trùng nhau"
            result_rows.append(row)
        log_lines.append("Nguồn và đích đang trùng nhau, không thực hiện chuyển.")
        return jsonify({"ok": False, "rows": result_rows, "log": "\n".join(log_lines)})

    try:
        dest_account = payload["dest_account"]
        state = prepared_transfers[payload["prepare_id"]]
        dst = login_hncode(TARGETS[dest]["base_url"], dest_account["username"], dest_account["password"])
        out_dir = state["root"]
        language_ids = language_ids_for_target(dest, settings.get("languages", []))

        for row in rows:
            row = dict(row)
            if not row.get("selected"):
                row["status"] = "Bỏ qua"
                result_rows.append(row)
                continue
            try:
                item = state["items"].get(row["original_code"])
                if not item:
                    raise RuntimeError("Chưa đọc được dữ liệu nguồn cho bài này")
                info = item["info"]
                zip_path = item["zip_path"]
                cases = item["cases"]
                dest_code = row["code"] or row["original_code"]
                if row.get("name"):
                    info.name = row["name"]
                info.time_limit = row.get("time_limit") or settings.get("time_limit") or info.time_limit or "1.0"
                info.memory_limit = row.get("memory_limit") or settings.get("memory_limit") or info.memory_limit or "1048576"
                if dest == "tinhoctre":
                    upload_transfer_to_tinhoctre(dst, dest, dest_code, info, zip_path, cases, row, out_dir, language_ids, log_lines)
                else:
                    upload_transfer_to_dmoj(dst, dest, dest_code, info, zip_path, cases, row, language_ids, log_lines)
                row["status"] = "✓ Thành công"
                row["link"] = problem_url(TARGETS[dest]["base_url"], dest_code)
            except ProblemAlreadyExists as exc:
                row["status"] = "✗ Bài đã tồn tại"
                log_lines.append(f"✗ {row.get('code')}: {exc}. Bỏ qua bài này và tiếp tục các bài khác.")
            except Exception as exc:
                row["status"] = "✗ Lỗi"
                log_lines.append(f"✗ {row.get('code')}: {exc}")
            result_rows.append(row)
        ok = all((not row.get("selected")) or row["status"].startswith("✓") for row in result_rows)
        return jsonify({"ok": ok, "rows": result_rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


def upload_transfer_to_dmoj(session, dest: str, dest_code: str, info: ProblemInfo, zip_path: Path, cases, row: dict, language_ids: list[str], log_lines: list[str]) -> None:
    base_url = TARGETS[dest]["base_url"]
    exists = destination_problem_exists(session, base_url, dest_code)
    if exists:
        raise ProblemAlreadyExists(f"Mã bài {dest_code} đã tồn tại tại {problem_url(base_url, dest_code)}")
    if row.get("upload_statement") and not exists:
        dest_info = problem_info_for_target(info, dest)
        create_hncode_problem(
            session,
            base_url,
            dest_info,
            dest_code=dest_code,
            type_id=TARGETS[dest]["type_id"],
            group_id=TARGETS[dest]["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{dest_code}: đã tạo đề.")
    else:
        log_lines.append(f"{dest_code}: bỏ qua tạo đề.")
    if row.get("upload_tests"):
        upload_hncode_tests(session, base_url, dest_code, zip_path, cases)
        log_lines.append(f"{dest_code}: đã upload test.")
    else:
        log_lines.append(f"{dest_code}: không upload test.")


def upload_transfer_to_tinhoctre(session, dest: str, dest_code: str, info: ProblemInfo, zip_path: Path, cases, row: dict, out_dir: Path, language_ids: list[str], log_lines: list[str]) -> None:
    base_url = TARGETS[dest]["base_url"]
    statement = out_dir / f"{dest_code}.md"
    dest_info = problem_info_for_target(info, dest)
    statement.write_text(dest_info.description, encoding="utf-8")
    bundle = ProblemBundle(0, dest_code, info.name, statement, None, zip_path, None)
    tests = GeneratedTests(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
    exists = tinhoctre_problem_exists(session, base_url, dest_code)
    if exists:
        raise ProblemAlreadyExists(f"Mã bài {dest_code} đã tồn tại tại {problem_url(base_url, dest_code)}")
    if row.get("upload_statement") and not exists:
        create_hncode_problem(
            session,
            base_url,
            dest_info,
            dest_code=dest_code,
            type_id=TARGETS[dest]["type_id"],
            group_id=TARGETS[dest]["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{dest_code}: đã tạo đề.")
    else:
        log_lines.append(f"{dest_code}: bỏ qua tạo đề.")
    if row.get("upload_tests"):
        upload_tinhoctre_tests(session, base_url, dest_code, tests)
        log_lines.append(f"{dest_code}: đã upload test.")
    else:
        log_lines.append(f"{dest_code}: không upload test.")


if __name__ == "__main__":
    app.run(
        host=os.getenv("TOOL_OJ_HOST", "127.0.0.1"),
        port=int(os.getenv("TOOL_OJ_PORT", "5050")),
        debug=False,
    )
