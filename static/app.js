const TARGETS = window.APP_CONFIG.targets;
let preparedUpload = null;
let preparedSingleUpload = null;
let preparedTransfer = null;
let preparedContestTransfer = null;
let preparedQuiz = null;
let preparedContestLessonCopy = null;
let preparedCourseClone = null;
let preparedGrading = null;
let selectedZipFile = null;
let selectedSingleTestZipFile = null;
let selectedGradingZipFile = null;
let selectedGradingCsvFile = null;
const QUIZ_FORMAT_GUIDE = window.APP_CONFIG.quizFormatGuide;

const logEl = document.getElementById("log");
const statusEl = document.getElementById("jobStatus");
let logText = "Sẵn sàng.";
const progressTimers = new Map();
function colorizeLog(text) {
  return String(text).split("\n").map(line => {
    const trimmed = line.trim();
    let cls = "";
    if (trimmed.startsWith("✓") || trimmed.includes("Thành công") || trimmed.includes("Đã tạo") || trimmed.includes("Đã upload")) cls = "log-ok";
    else if (trimmed.startsWith("✗") || trimmed.startsWith("Error:") || trimmed.includes("Lỗi")) cls = "log-err";
    else if (trimmed.includes("đã tồn tại") || trimmed.includes("Đã tồn tại") || trimmed.includes("Bài đã tồn tại") || trimmed.includes("Contest đã tồn tại")) cls = "log-warn";
    else if (trimmed.startsWith("Tiến độ:") || trimmed.startsWith("Đang ")) cls = "log-progress";
    const safe = escapeHtml(line);
    return cls ? `<span class="${cls}">${safe}</span>` : safe;
  }).join("\n");
}
function renderLog() { logEl.innerHTML = colorizeLog(logText); logEl.scrollTop = logEl.scrollHeight; }
function log(text) { logText = String(text); renderLog(); }
function append(text) { logText += "\n" + String(text); renderLog(); }
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
  tinhoctre_cookie: document.getElementById("acct_tinhoctre_cookie"),
  contest_hnoj_user: document.getElementById("acct_contest_hnoj_user"),
  contest_hnoj_pass: document.getElementById("acct_contest_hnoj_pass"),
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
document.getElementById("checkAccounts").onclick = () => { log("Đang kiểm tra đăng nhập các trang..."); checkAllAccounts(); };
document.getElementById("openTinHocTreBrowser").onclick = async () => {
  try {
    status("running");
    const data = await postJson("/api/tinhoctre-browser/start", {});
    append(data.message || "Đã mở Edge đăng nhập TinHocTre.");
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("pullTinHocTreCookie").onclick = async () => {
  try {
    status("running");
    const data = await postJson("/api/tinhoctre-browser/cookie", {});
    accountFields.tinhoctre_cookie.value = data.cookie || "";
    saveAccounts();
    append(data.message || "Đã lấy và lưu Cookie TinHocTre.");
    await checkLogin("tinhoctre", "login_tinhoctre", firstToken(document.getElementById("transferCodes").value));
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("quickTinHocTreCookie").onclick = async () => {
  try {
    status("running");
    append("Đang đóng/mở lại Edge để lấy cookie TinHocTre...");
    const data = await postJson("/api/tinhoctre-browser/quick-cookie", {});
    accountFields.tinhoctre_cookie.value = data.cookie || "";
    saveAccounts();
    append(data.message || "Đã lấy và lưu Cookie TinHocTre từ Edge.");
    await checkLogin("tinhoctre", "login_tinhoctre", firstToken(document.getElementById("transferCodes").value));
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("clearAccounts").onclick = () => {
  for (const key of Object.keys(accountFields)) localStorage.removeItem("chuyenbai." + key);
  for (const [key, input] of Object.entries(accountFields)) if (key.endsWith("_pass") || key.endsWith("_cookie")) input.value = "";
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
function localDateTimeValue(date) {
  const pad = value => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function backendDateTimeValue(value) {
  if (!value) return "";
  return value.length === 16 ? value.replace("T", " ") + ":00" : value.replace("T", " ");
}
function setContestTime(dayOffset=0, startHour=8, startMinute=0, durationMinutes=180) {
  const start = new Date();
  start.setDate(start.getDate() + dayOffset);
  start.setHours(startHour, startMinute, 0, 0);
  const end = new Date(start.getTime() + durationMinutes * 60000);
  document.getElementById("createContestStart").value = localDateTimeValue(start);
  document.getElementById("createContestEnd").value = localDateTimeValue(end);
}
document.getElementById("contestTimeToday").onclick = () => setContestTime(0, 8, 0, 180);
document.getElementById("contestTimeTomorrow").onclick = () => setContestTime(1, 8, 0, 180);
document.getElementById("contestTime90").onclick = () => {
  const startInput = document.getElementById("createContestStart");
  const start = startInput.value ? new Date(startInput.value) : new Date();
  document.getElementById("createContestStart").value = localDateTimeValue(start);
  document.getElementById("createContestEnd").value = localDateTimeValue(new Date(start.getTime() + 90 * 60000));
};
document.getElementById("chooseZip").onclick = () => document.getElementById("zipFileInput").click();
document.getElementById("zipFileInput").onchange = event => {
  selectedZipFile = event.target.files[0] || null;
  if (selectedZipFile) document.getElementById("uploadZip").value = selectedZipFile.name;
};
document.getElementById("useBatchSample").onclick = async () => {
  selectedZipFile = null;
  document.getElementById("zipFileInput").value = "";
  const data = await postJson("/api/sample/tonghaiso", {});
  document.getElementById("uploadZip").value = data.zip_path;
  append("Đã điền file mẫu Tổng hai số cho Up nhiều bài.");
};
function toggleBox(buttonId, boxId, openText, closedText) {
  const box = document.getElementById(boxId);
  box.classList.toggle("hidden");
  document.getElementById(buttonId).textContent = box.classList.contains("hidden") ? openText : closedText;
}
document.getElementById("toggleSingleStatement").onclick = () => toggleBox("toggleSingleStatement", "singleStatementBox", "Mở đề bài", "Thu gọn đề bài");
document.getElementById("toggleSingleGenerator").onclick = () => toggleBox("toggleSingleGenerator", "singleGeneratorBox", "Mở sinh test", "Thu gọn sinh test");
document.getElementById("toggleSingleSolution").onclick = () => toggleBox("toggleSingleSolution", "singleSolutionBox", "Mở lời giải", "Thu gọn lời giải");
document.getElementById("chooseSingleStatement").onclick = () => document.getElementById("singleStatementFile").click();
document.getElementById("chooseSingleGenerator").onclick = () => document.getElementById("singleGeneratorFile").click();
document.getElementById("chooseSingleTestZip").onclick = () => document.getElementById("singleTestZipFile").click();
document.getElementById("chooseSingleSolution").onclick = () => document.getElementById("singleSolutionFile").click();
document.getElementById("useSingleSample").onclick = async () => {
  const data = await postJson("/api/sample/tonghaiso", {});
  document.getElementById("singleCode").value = data.code;
  document.getElementById("singleName").value = data.name;
  document.getElementById("singlePoints").value = data.points || "100";
  document.getElementById("singleTags").value = data.tags || "";
  document.getElementById("singleTimeLimit").value = "1.0";
  document.getElementById("singleMemoryLimit").value = "1024M";
  document.getElementById("singlePartial").checked = true;
  document.getElementById("singleStatement").value = data.statement || "";
  document.getElementById("singleGenerator").value = data.generator || "";
  document.getElementById("singleGeneratorName").value = "gentest_" + data.code + ".py";
  document.getElementById("singleSolution").value = data.solution_md || "";
  selectedSingleTestZipFile = null;
  document.getElementById("singleTestZipFile").value = "";
  document.getElementById("singleTestZipName").value = "Có zip test trong mẫu; Up 1 bài sẽ sinh từ gentest";
  append("Đã nạp mẫu Tổng hai số vào Up 1 bài. Bấm Chuẩn bị dữ liệu để kiểm tra.");
};
document.getElementById("singleStatementFile").addEventListener("change", async event => {
  const file = event.target.files && event.target.files[0];
  if (file) document.getElementById("singleStatement").value = await file.text();
});
document.getElementById("singleGeneratorFile").addEventListener("change", async event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("singleGeneratorName").value = file ? file.name : "";
  if (file) document.getElementById("singleGenerator").value = await file.text();
});
document.getElementById("singleTestZipFile").addEventListener("change", event => {
  selectedSingleTestZipFile = event.target.files && event.target.files[0] || null;
  document.getElementById("singleTestZipName").value = selectedSingleTestZipFile ? selectedSingleTestZipFile.name : "";
});
document.getElementById("singleSolutionFile").addEventListener("change", async event => {
  const file = event.target.files && event.target.files[0];
  if (file) document.getElementById("singleSolution").value = await file.text();
});

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
function renderSingleLanguages() {
  const target = document.getElementById("singleUploadTarget").value;
  const langs = TARGETS[target].languages;
  document.getElementById("singleLanguages").innerHTML = Object.keys(langs).map(name =>
    `<label class="check"><input type="checkbox" value="${name}" checked> ${name}</label>`
  ).join("");
}
document.getElementById("uploadTarget").addEventListener("change", renderLanguages);
document.getElementById("singleUploadTarget").addEventListener("change", renderSingleLanguages);
document.getElementById("transferDest").addEventListener("change", renderTransferLanguages);
document.getElementById("uploadTarget").addEventListener("change", checkUploadLogin);
document.getElementById("singleUploadTarget").addEventListener("change", checkSingleUploadLogin);
document.getElementById("transferSource").addEventListener("change", checkTransferLogins);
document.getElementById("transferDest").addEventListener("change", checkTransferLogins);
document.getElementById("transferCodes").addEventListener("blur", checkTransferLogins);
document.getElementById("contestSource").addEventListener("change", checkContestLogins);
document.getElementById("contestDest").addEventListener("change", checkContestLogins);
document.getElementById("contestCodes").addEventListener("blur", checkContestLogins);
document.getElementById("createContestTarget").addEventListener("change", checkCreateContestLogin);
document.getElementById("lessonCopySource").addEventListener("change", checkLessonCopyLogin);
document.getElementById("lessonCopyContestUrl").addEventListener("blur", () => {
  const value = document.getElementById("lessonCopyContestUrl").value.toLowerCase();
  if (value.includes("hnoj.edu.vn")) document.getElementById("lessonCopySource").value = "hnoj";
  if (value.includes("hncode.edu.vn") || value.includes("oj.hncode.edu.vn")) document.getElementById("lessonCopySource").value = "hncode";
  checkLessonCopyLogin();
});
renderLanguages();
renderSingleLanguages();
renderTransferLanguages();
setTimeout(() => { checkUploadLogin(); checkSingleUploadLogin(); checkTransferLogins(); checkContestLogins(); checkCreateContestLogin(); checkQuizLogin(); checkLessonCopyLogin(); checkCourseCloneLogin(); }, 300);

function selectedLanguages() {
  return [...document.querySelectorAll("#languages input:checked")].map(item => item.value);
}
function selectedSingleLanguages() {
  return [...document.querySelectorAll("#singleLanguages input:checked")].map(item => item.value);
}
function selectedTransferLanguages() {
  return [...document.querySelectorAll("#transferLanguages input:checked")].map(item => item.value);
}
function accountPayload(target) {
  const payload = {
    username: accountFields[target + "_user"].value,
    password: accountFields[target + "_pass"].value,
  };
  if (target === "tinhoctre") payload.cookie = accountFields.tinhoctre_cookie.value;
  return payload;
}
function firstToken(value) {
  return (value || "").split(/[\s,]+/).filter(Boolean)[0] || "";
}
function setLoginBadge(id, state, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = "login-badge " + (state || "");
}
async function checkLogin(target, badgeId, probeCode="") {
  setLoginBadge(badgeId, "", "Đang kiểm tra...");
  try {
    const data = await postJson("/api/check-login", {target, account: accountPayload(target), probe_code: probeCode});
    setLoginBadge(badgeId, data.ok ? "ok" : "err", data.ok ? "✓ Đăng nhập OK" : "✗ " + (data.message || "Lỗi"));
    return data.ok;
  } catch (err) {
    setLoginBadge(badgeId, "err", "✗ " + String(err).replace(/^Error:\s*/, ""));
    return false;
  }
}
async function checkHncodeOjLogin(badgeId) {
  setLoginBadge(badgeId, "", "Đang kiểm tra...");
  try {
    const data = await postJson("/api/check-login", {target: "hncode_oj", account: accountPayload("hncode")});
    setLoginBadge(badgeId, data.ok ? "ok" : "err", data.ok ? "✓ Đăng nhập OK" : "✗ " + (data.message || "Lỗi"));
    return data.ok;
  } catch (err) {
    setLoginBadge(badgeId, "err", "✗ " + String(err).replace(/^Error:\s*/, ""));
    return false;
  }
}
async function checkAllAccounts() {
  saveAccounts();
  await Promise.all([
    checkLogin("hnoj", "login_hnoj"),
    checkLogin("hncode", "login_hncode"),
    checkLogin("tinhoctre", "login_tinhoctre", firstToken(document.getElementById("transferCodes").value)),
    checkLogin("contest_hnoj", "login_contest_hnoj"),
  ]);
}
function checkUploadLogin() {
  checkLogin(document.getElementById("uploadTarget").value, "uploadTargetLogin");
}
function checkSingleUploadLogin() {
  checkLogin(document.getElementById("singleUploadTarget").value, "singleUploadLogin");
}
function checkTransferLogins() {
  const probe = firstToken(document.getElementById("transferCodes").value);
  checkLogin(document.getElementById("transferSource").value, "transferSourceLogin", probe);
  checkLogin(document.getElementById("transferDest").value, "transferDestLogin");
}
function checkContestLogins() {
  checkLogin(document.getElementById("contestSource").value, "contestSourceLogin");
  checkLogin(document.getElementById("contestDest").value, "contestDestLogin");
}
function checkCreateContestLogin() {
  checkLogin(document.getElementById("createContestTarget").value, "createContestLogin");
}
function checkQuizLogin() {
  document.getElementById("quizUserMirror").value = accountFields.hncode_user.value || "hncode";
  checkHncodeOjLogin("quizLogin");
}
function checkLessonCopyLogin() {
  document.getElementById("lessonCopyUserMirror").value = accountFields.hncode_user.value || "hncode";
  const source = document.getElementById("lessonCopySource").value;
  checkLogin(source, "lessonCopySourceLogin");
  checkLogin("hncode", "lessonCopyLogin");
}
function checkCourseCloneLogin() {
  document.getElementById("courseCloneUserMirror").value = accountFields.hncode_user.value || "hncode";
  checkLogin("hncode", "courseCloneLogin");
}
function uploadSettings() {
  const target = document.getElementById("uploadTarget").value;
  return {
    target,
    zip_path: selectedZipFile ? "" : document.getElementById("uploadZip").value,
    creator: document.getElementById("creator").value,
    points: document.getElementById("uploadPoints").value.trim() || "100",
    tags: document.getElementById("uploadTags").value.trim(),
    partial: document.getElementById("uploadPartial").checked,
    time_limit: document.getElementById("timeLimit").value,
    memory_limit: document.getElementById("memoryLimit").value,
    languages: selectedLanguages(),
    no_submit: document.getElementById("noSubmit").checked,
    submit_cpp: document.getElementById("submitCpp").checked,
    submit_python: document.getElementById("submitPython").checked,
    skip_statement_title: document.getElementById("skipStatementTitle").checked,
    overwrite_existing: document.getElementById("overwriteExisting").checked,
    overwrite_statement: document.getElementById("overwriteStatement").checked,
    overwrite_tests: document.getElementById("overwriteTests").checked,
    ...accountPayload(target),
  };
}
function singleUploadSettings() {
  const target = document.getElementById("singleUploadTarget").value;
  return {
    target,
    code: document.getElementById("singleCode").value.trim(),
    name: document.getElementById("singleName").value.trim(),
    points: document.getElementById("singlePoints").value.trim() || "100",
    tags: document.getElementById("singleTags").value.trim(),
    time_limit: document.getElementById("singleTimeLimit").value.trim() || "1.0",
    memory_limit: document.getElementById("singleMemoryLimit").value.trim() || "1024M",
    partial: document.getElementById("singlePartial").checked,
    overwrite_statement: document.getElementById("singleOverwrite").checked,
    overwrite_tests: document.getElementById("singleOverwrite").checked,
    languages: selectedSingleLanguages(),
    skip_statement_title: document.getElementById("singleSkipStatementTitle").checked,
    statement_text: document.getElementById("singleStatement").value,
    generator_text: document.getElementById("singleGenerator").value,
    generator_filename: document.getElementById("singleGeneratorName").value,
    solution_text: document.getElementById("singleSolution").value,
    upload_solution: Boolean(document.getElementById("singleSolution").value.trim()),
    no_submit: true,
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
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function parseJsonResponse(res) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch (err) {
    const preview = text.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);
    throw new Error(`Server trả về HTML/text thay vì JSON (HTTP ${res.status}). ${preview || "Không có nội dung lỗi."}`);
  }
}
async function prepareUploadRequest(settings) {
  if (!selectedZipFile) return postJson("/api/prepare-upload", settings);
  const form = new FormData();
  form.append("zip_file", selectedZipFile);
  form.append("payload", JSON.stringify(settings));
  const res = await fetch("/api/prepare-upload", {method:"POST", body:form});
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function prepareSingleUploadRequest(settings) {
  const form = new FormData();
  if (selectedSingleTestZipFile) form.append("test_zip", selectedSingleTestZipFile);
  form.append("payload", JSON.stringify(settings));
  const res = await fetch("/api/prepare-single-upload", {method:"POST", body:form});
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
function newProgressId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID().replaceAll("-", "");
  return Array.from({length: 32}, () => Math.floor(Math.random() * 16).toString(16)).join("");
}
function statusClass(text) {
  const value = String(text || "");
  if (value.startsWith("✓") || value.includes("Thành công") || value.includes("Đã đọc")) return "ok";
  if (value.includes("đã tồn tại") || value.includes("Đã tồn tại") || value.includes("đã có") || value.includes("Đã có")) return "warn";
  if (value.startsWith("✗") || value.includes("Lỗi")) return "err";
  return "";
}
function setStatusCell(cell, text, link="") {
  cell.className = "row-status " + statusClass(text);
  const linkHtml = link ? ` <a class="problem-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">Link</a>` : "";
  cell.innerHTML = `${escapeHtml(text || "")}${linkHtml}`;
}
function progressMessage(data) {
  const total = data.total || 0;
  const done = data.done || 0;
  const prefix = total ? `Tiến độ: ${done}/${total}` : "Tiến độ:";
  return data.message ? `${prefix} - ${data.message}` : prefix;
}
function startProgressPolling(progressId, tableSelector, mode="problem") {
  stopProgressPolling(progressId);
  const timer = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${progressId}`, {cache: "no-store"});
      if (!res.ok) return;
      const data = await res.json();
      if (data.rows) {
        if (mode === "contest") applyContestStatuses(data.rows);
        else if (mode === "grading") applyGradingStatuses(data.rows);
        else if (tableSelector) applyStatuses(data.rows, tableSelector);
      }
      if (data.message || data.total) append(progressMessage(data));
      if (data.finished) stopProgressPolling(progressId);
    } catch (err) {
      stopProgressPolling(progressId);
    }
  }, 1000);
  progressTimers.set(progressId, timer);
  return progressId;
}
function stopProgressPolling(progressId) {
  const timer = progressTimers.get(progressId);
  if (timer) clearInterval(timer);
  progressTimers.delete(progressId);
}

document.getElementById("prepareUpload").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuẩn bị dữ liệu...");
    startProgressPolling(progressId, "#uploadTable");
    const settings = uploadSettings();
    settings.progress_id = progressId;
    const data = await prepareUploadRequest(settings);
    stopProgressPolling(progressId);
    preparedUpload = data.prepare_id;
    renderUploadTable(data.rows);
    document.getElementById("confirmUpload").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

function renderUploadTable(rows) {
  const overwriteDefault = document.getElementById("overwriteExisting").checked;
  document.getElementById("uploadTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#uploadTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#uploadTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Điểm</th><th>Dạng bài tập / Tags</th><th>Time</th><th>Memory</th><th>Điểm thành phần</th><th>Ghi đè</th><th>Up đề</th><th>Up test</th><th>Up lời giải</th><th>File test</th><th>Số test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_code)}" data-source-time="${escapeHtml(row.source_time_limit || row.time_limit || "1.0")}" data-source-memory="${escapeHtml(row.source_memory_limit || row.memory_limit || "1048576")}">
      <td><input type="checkbox" class="row-selected" checked></td>
      <td><input type="text" class="row-code" value="${escapeHtml(row.code)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name)}"></td>
      <td><input type="text" class="row-points" value="${escapeHtml(row.points || "100")}"></td>
      <td><input type="text" class="row-tags" value="${escapeHtml(row.tags || "")}"></td>
      <td><input type="text" class="row-time" value="${escapeHtml(row.time_limit || "1.0")}"></td>
      <td><input type="text" class="row-memory" value="${escapeHtml(row.memory_limit || "1048576")}"></td>
      <td><input type="checkbox" class="row-partial" ${row.partial === false ? "" : "checked"}></td>
      <td><input type="checkbox" class="row-overwrite" ${row.overwrite_default === true || overwriteDefault ? "checked" : ""}></td>
      <td><input type="checkbox" class="row-statement" checked></td>
      <td><input type="checkbox" class="row-tests" ${row.upload_tests_default === false ? "" : "checked"}></td>
      <td><input type="checkbox" class="row-solution" ${row.upload_solution_default ? "checked" : ""}></td>
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
    points: tr.querySelector(".row-points").value.trim(),
    tags: tr.querySelector(".row-tags").value.trim(),
    time_limit: tr.querySelector(".row-time").value.trim(),
    memory_limit: tr.querySelector(".row-memory").value.trim(),
    partial: tr.querySelector(".row-partial").checked,
    overwrite: tr.querySelector(".row-overwrite").checked,
    upload_statement: tr.querySelector(".row-statement").checked,
    upload_tests: tr.querySelector(".row-tests").checked,
    upload_solution: tr.querySelector(".row-solution").checked,
  }));
}
document.getElementById("confirmUpload").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang up bài...");
    markRowsProcessing("#uploadTable", "Đang up...");
    startProgressPolling(progressId, "#uploadTable");
    const settings = uploadSettings();
    settings.progress_id = progressId;
    const data = await postJson("/api/confirm-upload", {prepare_id: preparedUpload, settings, rows: collectUploadRows(), progress_id: progressId});
    stopProgressPolling(progressId);
    applyStatuses(data.rows, "#uploadTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareSingleUpload").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuẩn bị dữ liệu 1 bài...");
    const settings = singleUploadSettings();
    settings.progress_id = progressId;
    const data = await prepareSingleUploadRequest(settings);
    preparedSingleUpload = data.prepare_id;
    renderSingleUploadTable(data.rows || []);
    document.getElementById("confirmSingleUpload").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    preparedSingleUpload = null;
    document.getElementById("confirmSingleUpload").disabled = true;
    log(String(err));
    status("failed", "err");
  }
};

function renderSingleUploadTable(rows) {
  document.getElementById("singleUploadTable").innerHTML = `<table>
    <thead><tr><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Điểm</th><th>Dạng bài tập / Tags</th><th>Time</th><th>Memory</th><th>Điểm thành phần</th><th>Up đề</th><th>Up test</th><th>Up lời giải</th><th>Test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_code)}">
      <td><input type="checkbox" class="row-selected" checked></td>
      <td><input type="text" class="row-code" value="${escapeHtml(row.code)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name)}"></td>
      <td><input type="text" class="row-points" value="${escapeHtml(row.points || "100")}"></td>
      <td><input type="text" class="row-tags" value="${escapeHtml(row.tags || "")}"></td>
      <td><input type="text" class="row-time" value="${escapeHtml(row.time_limit || "1.0")}"></td>
      <td><input type="text" class="row-memory" value="${escapeHtml(row.memory_limit || "1024M")}"></td>
      <td><input type="checkbox" class="row-partial" ${row.partial === false ? "" : "checked"}></td>
      <td><input type="checkbox" class="row-statement" ${row.upload_statement_default ? "checked" : ""}></td>
      <td><input type="checkbox" class="row-tests" ${row.upload_tests_default ? "checked" : ""}></td>
      <td><input type="checkbox" class="row-solution" ${row.upload_solution_default ? "checked" : ""}></td>
      <td><div class="test-meta">${escapeHtml(row.test_file || "Không có test")}<br>${escapeHtml(row.test_count || 0)} test</div></td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "Đã chuẩn bị")}</td>
    </tr>`).join("")}</tbody></table>`;
}

function collectSingleUploadRows() {
  return [...document.querySelectorAll("#singleUploadTable tbody tr")].map(tr => ({
    original_code: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    code: tr.querySelector(".row-code").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    points: tr.querySelector(".row-points").value.trim(),
    tags: tr.querySelector(".row-tags").value.trim(),
    time_limit: tr.querySelector(".row-time").value.trim(),
    memory_limit: tr.querySelector(".row-memory").value.trim(),
    partial: tr.querySelector(".row-partial").checked,
    upload_statement: tr.querySelector(".row-statement").checked,
    upload_tests: tr.querySelector(".row-tests").checked,
    upload_solution: tr.querySelector(".row-solution").checked,
  }));
}

document.getElementById("confirmSingleUpload").onclick = async () => {
  const progressId = newProgressId();
  try {
    if (!preparedSingleUpload) throw new Error("Hãy bấm Chuẩn bị dữ liệu trước khi xác nhận up.");
    status("running");
    log("Đang up 1 bài...");
    markRowsProcessing("#singleUploadTable", "Đang up...");
    startProgressPolling(progressId, "#singleUploadTable");
    const settings = singleUploadSettings();
    settings.progress_id = progressId;
    const data = await postJson("/api/confirm-single-upload", {prepare_id: preparedSingleUpload, settings, rows: collectSingleUploadRows(), progress_id: progressId});
    stopProgressPolling(progressId);
    applyStatuses(data.rows || [], "#singleUploadTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang đọc dữ liệu bài nguồn...");
    const source = document.getElementById("transferSource").value;
    const dest = document.getElementById("transferDest").value;
    const codes = document.getElementById("transferCodes").value.split(/[\s,]+/).filter(Boolean);
    startProgressPolling(progressId, "#transferTable");
    const data = await postJson("/api/prepare-transfer", {
      source, dest, codes,
      source_account: accountPayload(source),
      settings: transferSettings(),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    preparedTransfer = data.prepare_id;
    renderTransferTable(data.rows);
    document.getElementById("confirmTransfer").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
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
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuyển bài...");
    const source = document.getElementById("transferSource").value;
    const dest = document.getElementById("transferDest").value;
    markRowsProcessing("#transferTable", "Đang chuyển...");
    startProgressPolling(progressId, "#transferTable");
    const data = await postJson("/api/confirm-transfer", {
      prepare_id: preparedTransfer,
      source, dest, rows: collectRows("#transferTable"),
      settings: transferSettings(),
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    applyStatuses(data.rows, "#transferTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareContestTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang đọc dữ liệu contest nguồn...");
    const source = document.getElementById("contestSource").value;
    const dest = document.getElementById("contestDest").value;
    const codes = document.getElementById("contestCodes").value.split(/[\s,]+/).filter(Boolean);
    startProgressPolling(progressId, "#contestTransferTable", "contest");
    const data = await postJson("/api/prepare-contest-transfer", {
      source, dest, codes,
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
      settings: contestTransferSettings(),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    preparedContestTransfer = data.prepare_id;
    renderContestTransferTable(data.rows);
    document.getElementById("confirmContestTransfer").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("confirmContestTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuyển contest...");
    const source = document.getElementById("contestSource").value;
    const dest = document.getElementById("contestDest").value;
    markRowsProcessing("#contestTransferTable", "Đang chuyển...");
    startProgressPolling(progressId, "#contestTransferTable", "contest");
    const data = await postJson("/api/confirm-contest-transfer", {
      prepare_id: preparedContestTransfer,
      source, dest, rows: collectContestRows(),
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
      settings: contestTransferSettings(),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    applyContestStatuses(data.rows);
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("createContestButton").onclick = async () => {
  try {
    status("running");
    log("Đang tạo contest...");
    const target = document.getElementById("createContestTarget").value;
    const data = await postJson("/api/create-contest", {
      target,
      account: accountPayload(target),
      key: document.getElementById("createContestKey").value.trim(),
      name: document.getElementById("createContestName").value.trim(),
      start_time: backendDateTimeValue(document.getElementById("createContestStart").value.trim()),
      end_time: backendDateTimeValue(document.getElementById("createContestEnd").value.trim()),
      problems: document.getElementById("createContestProblems").value.split(/[\s,]+/).filter(Boolean),
    });
    log(data.log);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareContestLessonCopy").onclick = async () => {
  try {
    status("running");
    log("Đang đọc danh sách bài trong contest và lesson đích...");
    saveAccounts();
    const source = document.getElementById("lessonCopySource").value;
    const data = await postJson("/api/prepare-contest-to-lesson", {
      source,
      source_account: accountPayload(source),
      account: accountPayload("hncode"),
      contest_url: document.getElementById("lessonCopyContestUrl").value.trim(),
      lesson_url: document.getElementById("lessonCopyLessonUrl").value.trim(),
    });
    preparedContestLessonCopy = data.prepare_id;
    renderContestLessonCopyTable(data.rows || []);
    document.getElementById("confirmContestLessonCopy").disabled = !data.can_copy;
    log(data.log);
    status(data.can_copy ? "ready" : "done", data.can_copy ? "ok" : "warn");
  } catch (err) {
    preparedContestLessonCopy = null;
    document.getElementById("confirmContestLessonCopy").disabled = true;
    document.getElementById("contestLessonCopyTable").innerHTML = "";
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("confirmContestLessonCopy").onclick = async () => {
  try {
    if (!preparedContestLessonCopy) throw new Error("Hãy bấm Chuẩn bị dữ liệu trước khi sao chép bài.");
    status("running");
    log("Đang sao chép bài vào lesson HNCode...");
    markRowsProcessing("#contestLessonCopyTable", "Đang thêm...");
    saveAccounts();
    const source = document.getElementById("lessonCopySource").value;
    const res = await fetch("/api/confirm-contest-to-lesson", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({
      prepare_id: preparedContestLessonCopy,
      source_account: accountPayload(source),
      account: accountPayload("hncode"),
      rows: collectContestLessonCopyRows(),
    })});
    const data = await parseJsonResponse(res);
    applyContestLessonCopyStatuses(data.rows || []);
    if (!res.ok) throw new Error(data.error || "Không sao chép được bài vào lesson.");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("fillLessonCopyScores").onclick = () => {
  const value = document.getElementById("lessonCopyBulkScore").value.trim();
  if (!value) {
    log("Hãy nhập điểm chung trước khi áp dụng.");
    status("failed", "err");
    return;
  }
  document.querySelectorAll("#contestLessonCopyTable .row-score").forEach(input => { input.value = value; });
  append(`Đã áp dụng điểm ${value} cho tất cả bài trong bảng Contest → Lesson.`);
};

function renderContestLessonCopyTable(rows) {
  document.getElementById("contestLessonCopyTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#contestLessonCopyTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#contestLessonCopyTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>STT</th><th>Mã bài</th><th>Tên bài</th><th>Điểm lesson</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-code="${escapeHtml(row.code)}">
      <td><input type="checkbox" class="row-selected" ${row.selected ? "checked" : ""} ${row.problem_id ? "" : "disabled"}></td>
      <td>${escapeHtml(row.index || "")}</td>
      <td><a class="problem-link" href="https://hncode.edu.vn/problem/${escapeHtml(row.code)}" target="_blank" rel="noopener">${escapeHtml(row.code)}</a></td>
      <td>${escapeHtml(row.title || "")}</td>
      <td><input type="text" class="row-score" value="${escapeHtml(row.score || "100")}"></td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}</td>
    </tr>`).join("")}</tbody></table>`;
}

function collectContestLessonCopyRows() {
  return [...document.querySelectorAll("#contestLessonCopyTable tbody tr")].map(tr => ({
    code: tr.dataset.code,
    selected: tr.querySelector(".row-selected").checked,
    score: tr.querySelector(".row-score").value.trim(),
  }));
}

function applyContestLessonCopyStatuses(rows) {
  const byCode = new Map(rows.map(row => [row.code, row]));
  for (const tr of document.querySelectorAll("#contestLessonCopyTable tbody tr")) {
    const row = byCode.get(tr.dataset.code);
    if (!row) continue;
    const detail = row.error ? "\n" + row.error : "";
    setStatusCell(tr.querySelector(".row-status"), (row.status || "") + detail, row.link || "");
  }
}

document.getElementById("prepareCourseClone").onclick = async () => {
  try {
    status("running");
    log("Đang đọc lesson và contest của course nguồn...");
    saveAccounts();
    const data = await postJson("/api/prepare-course-clone", {
      account: accountPayload("hncode"),
      source_url: document.getElementById("courseCloneSourceUrl").value.trim(),
      dest_url: document.getElementById("courseCloneDestUrl").value.trim(),
      contest_suffix: document.getElementById("courseCloneContestSuffix").value.trim(),
      include_lessons: document.getElementById("courseCloneLessons").checked,
      include_contests: document.getElementById("courseCloneContests").checked,
    });
    preparedCourseClone = data.prepare_id;
    renderCourseCloneTable(data.rows || []);
    document.getElementById("confirmCourseClone").disabled = !data.can_clone;
    log(data.log);
    status(data.can_clone ? "ready" : "done", data.can_clone ? "ok" : "warn");
  } catch (err) {
    preparedCourseClone = null;
    document.getElementById("confirmCourseClone").disabled = true;
    document.getElementById("courseCloneTable").innerHTML = "";
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("confirmCourseClone").onclick = async () => {
  try {
    if (!preparedCourseClone) throw new Error("Hãy bấm Chuẩn bị dữ liệu trước khi Clone Course.");
    status("running");
    log("Đang clone course HNCode...");
    markRowsProcessing("#courseCloneTable", "Đang clone...");
    saveAccounts();
    const res = await fetch("/api/confirm-course-clone", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({
      prepare_id: preparedCourseClone,
      account: accountPayload("hncode"),
      rows: collectCourseCloneRows(),
    })});
    const data = await parseJsonResponse(res);
    applyCourseCloneStatuses(data.rows || []);
    if (!res.ok) throw new Error(data.error || "Không clone được course.");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

function renderCourseCloneTable(rows) {
  document.getElementById("courseCloneTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#courseCloneTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#courseCloneTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Loại</th><th>Thứ tự</th><th>Mã/ID nguồn</th><th>Tên</th><th>Mã contest đích</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-kind="${escapeHtml(row.kind)}" data-key="${escapeHtml(row.key)}">
      <td><input type="checkbox" class="row-selected" ${row.selected ? "checked" : ""} ${row.can_clone ? "" : "disabled"}></td>
      <td>${row.kind === "contest" ? "Contest" : "Lesson"}</td>
      <td>${escapeHtml(row.order || "")}</td>
      <td>${escapeHtml(row.key || "")}</td>
      <td>${escapeHtml(row.title || "")}</td>
      <td>${row.kind === "contest" ? `<input type="text" class="row-new-key" value="${escapeHtml(row.new_key || "")}">` : ""}</td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}</td>
    </tr>`).join("")}</tbody></table>`;
}

function collectCourseCloneRows() {
  return [...document.querySelectorAll("#courseCloneTable tbody tr")].map(tr => ({
    kind: tr.dataset.kind,
    key: tr.dataset.key,
    selected: tr.querySelector(".row-selected").checked,
    new_key: tr.querySelector(".row-new-key") ? tr.querySelector(".row-new-key").value.trim() : "",
  }));
}

function applyCourseCloneStatuses(rows) {
  const byId = new Map(rows.map(row => [row.kind + ":" + row.key, row]));
  for (const tr of document.querySelectorAll("#courseCloneTable tbody tr")) {
    const row = byId.get(tr.dataset.kind + ":" + tr.dataset.key);
    if (!row) continue;
    const detail = row.error ? "\n" + row.error : "";
    setStatusCell(tr.querySelector(".row-status"), (row.status || "") + detail, row.link || "");
  }
}

document.getElementById("chooseQuizFile").onclick = () => document.getElementById("quizFileInput").click();
document.getElementById("quizFileInput").addEventListener("change", async event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("quizFileName").value = file ? file.name : "";
  if (file) {
    document.getElementById("quizMarkdown").value = await file.text();
    preparedQuiz = null;
    document.getElementById("uploadQuizButton").disabled = true;
  }
});
document.getElementById("fillQuizSample").onclick = () => {
  document.getElementById("quizMarkdown").value = QUIZ_FORMAT_GUIDE;
  preparedQuiz = null;
  document.getElementById("uploadQuizButton").disabled = true;
};
document.getElementById("uploadQuizButton").disabled = true;
document.getElementById("quizMarkdown").addEventListener("input", () => {
  preparedQuiz = null;
  document.getElementById("uploadQuizButton").disabled = true;
});
document.getElementById("prepareQuizButton").onclick = async () => {
  try {
    status("running");
    log("Đang kiểm tra dữ liệu quiz...");
    const data = await postJson("/api/prepare-quiz", {text: document.getElementById("quizMarkdown").value});
    preparedQuiz = data.prepare_id;
    renderQuizTable(data.rows || []);
    log(data.log);
    document.getElementById("uploadQuizButton").disabled = !data.can_upload;
    status(data.can_upload ? "ready" : "failed", data.can_upload ? "ok" : "err");
  } catch (err) {
    preparedQuiz = null;
    document.getElementById("uploadQuizButton").disabled = true;
    document.getElementById("quizUploadSummary").innerHTML = "";
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("uploadQuizButton").onclick = async () => {
  try {
    if (!preparedQuiz) throw new Error("Hãy bấm Chuẩn bị dữ liệu trước khi up quiz.");
    status("running");
    log("Đang up list quiz lên HNCode...");
    saveAccounts();
    const data = await postJson("/api/upload-quiz", {
      prepare_id: preparedQuiz,
      account: accountPayload("hncode"),
      shuffle_choices: document.getElementById("quizShuffleChoices").checked,
      is_public: document.getElementById("quizPublic").checked,
    });
    const rows = (data.rows || []).map(row => `${row.status} ${row.index}. ${row.title}${row.link ? " - " + row.link : ""}`).join("\n");
    applyQuizStatuses(data.rows || []);
    document.getElementById("quizUploadSummary").innerHTML = `<div class="note">${escapeHtml(rows || data.log || "").replaceAll("\n", "<br>")}</div>`;
    log(data.log || rows);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

function renderQuizTable(rows) {
  document.getElementById("quizUploadSummary").innerHTML = `<table>
    <thead><tr><th>STT</th><th>Tiêu đề</th><th>Loại</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-quiz-index="${row.index}">
      <td>${row.index}</td>
      <td>${escapeHtml(row.title || "")}</td>
      <td>${escapeHtml(row.type || "")}</td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}${row.error ? `<div class="test-meta">${escapeHtml(row.error)}</div>` : ""}</td>
    </tr>`).join("")}</tbody>
  </table>`;
}

function applyQuizStatuses(rows) {
  const byIndex = new Map(rows.map(row => [String(row.index), row]));
  for (const tr of document.querySelectorAll("#quizUploadSummary tr[data-quiz-index]")) {
    const row = byIndex.get(tr.dataset.quizIndex);
    if (!row) continue;
    const cell = tr.querySelector(".row-status");
    cell.className = "row-status " + statusClass(row.status);
    const linkHtml = row.link ? ` <a class="problem-link" href="${escapeHtml(row.link)}" target="_blank" rel="noopener">Link</a>` : "";
    const errorHtml = row.error ? `<div class="test-meta">${escapeHtml(row.error)}</div>` : "";
    cell.innerHTML = `${escapeHtml(row.status || "")}${linkHtml}${errorHtml}`;
  }
}

function syncCodeListType() {
  const site = document.getElementById("codeListSite").value;
  const type = document.getElementById("codeListType");
  if (site === "hnoj") {
    type.value = "contest";
    [...type.options].forEach(option => option.disabled = option.value === "lesson");
    document.getElementById("codeListUrl").value = document.getElementById("codeListUrl").value || "https://hnoj.edu.vn/contest/ctp_4";
  } else {
    [...type.options].forEach(option => option.disabled = false);
  }
}
document.getElementById("codeListSite").addEventListener("change", syncCodeListType);
document.getElementById("runCodeList").onclick = async () => {
  try {
    status("running");
    saveAccounts();
    syncCodeListType();
    const site = document.getElementById("codeListSite").value;
    const sourceType = document.getElementById("codeListType").value;
    log("Đang lấy danh sách mã bài...");
    const data = await postJson("/api/misc/list-problem-codes", {
      site,
      source_type: sourceType,
      url: document.getElementById("codeListUrl").value.trim(),
      account: accountPayload(site),
    });
    document.getElementById("codeListOutput").value = data.codes_text || "";
    const rows = data.rows || [];
    document.getElementById("codeListSummary").innerHTML = `<div class="note">Tìm thấy ${rows.length} bài.</div>
      <table>
        <thead><tr><th>STT</th><th>Mã bài</th><th>Tên bài</th><th>Điểm</th></tr></thead>
        <tbody>${rows.map(row => `<tr>
          <td>${row.index || row.order || ""}</td>
          <td><code>${escapeHtml(row.code || "")}</code></td>
          <td>${escapeHtml(row.title || "")}</td>
          <td>${escapeHtml(row.points || row.score || "")}</td>
        </tr>`).join("")}</tbody>
      </table>`;
    log(data.log || `Đã lấy ${rows.length} mã bài.`);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
syncCodeListType();

document.getElementById("chooseLastSubZip").onclick = () => document.getElementById("lastSubZipFile").click();
document.getElementById("lastSubZipFile").addEventListener("change", event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("lastSubZipName").value = file ? file.name : "";
});
document.getElementById("runLastSubmissions").onclick = async () => {
  try {
    const input = document.getElementById("lastSubZipFile");
    const file = input.files && input.files[0];
    if (!file) throw new Error("Hãy chọn file zip data trước.");
    status("running");
    log("Đang xử lý last submissions...");
    const form = new FormData();
    form.append("zip_file", file);
    const res = await fetch("/api/misc/last-submissions", {method:"POST", body:form});
    if (!res.ok) {
      const data = await parseJsonResponse(res);
      throw new Error(data.error || "Không xử lý được file zip.");
    }
    const summaryRaw = res.headers.get("X-Last-Submissions-Summary") || "";
    const summary = summaryRaw ? JSON.parse(decodeURIComponent(summaryRaw)) : {};
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = summary.filename || "last_submissions.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    const text = `✓ Đã tạo file zip last submissions.\nTìm thấy: ${summary.found || 0}/${summary.total || 0} thí sinh\nThiếu file: ${summary.missing || 0}\nFile tải về: ${summary.filename || "last_submissions.zip"}`;
    document.getElementById("lastSubmissionsSummary").innerHTML = `<div class="note">${escapeHtml(text).replaceAll("\n", "<br>")}</div>`;
    log(text);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("chooseGradingZip").onclick = () => document.getElementById("gradingZipFile").click();
document.getElementById("chooseGradingCsv").onclick = () => document.getElementById("gradingCsvFile").click();
document.getElementById("gradingZipFile").addEventListener("change", event => {
  selectedGradingZipFile = event.target.files && event.target.files[0] || null;
  document.getElementById("gradingZipName").value = selectedGradingZipFile ? selectedGradingZipFile.name : "";
});
document.getElementById("gradingCsvFile").addEventListener("change", event => {
  selectedGradingCsvFile = event.target.files && event.target.files[0] || null;
  document.getElementById("gradingCsvName").value = selectedGradingCsvFile ? selectedGradingCsvFile.name : "";
});
function renderGradingTable(rows) {
  document.getElementById("gradingSummary").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#gradingSummary', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#gradingSummary', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Học sinh</th><th>Username</th><th>Mã bài</th><th>Tên bài</th><th>Điểm bài</th><th>File</th><th>%</th><th>Điểm</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_key)}">
      <td><input type="checkbox" class="row-selected" ${row.selected ? "checked" : ""}></td>
      <td>${escapeHtml(row.student || "")}</td>
      <td>${escapeHtml(row.username || "")}</td>
      <td>${escapeHtml(row.problem || "")}</td>
      <td>${escapeHtml(row.problem_title || "")}</td>
      <td>${escapeHtml(row.contest_points || "")}</td>
      <td><div class="test-meta">${escapeHtml(row.relative_path || row.file || "")}</div></td>
      <td class="row-percent">${escapeHtml(row.percent || "")}</td>
      <td class="row-score">${escapeHtml(row.score || "")}</td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}${row.submission_url ? ` <a class="problem-link" href="${escapeHtml(row.submission_url)}" target="_blank" rel="noopener">Link</a>` : ""}${row.message ? `<div class="test-meta">${escapeHtml(row.message)}</div>` : ""}</td>
    </tr>`).join("")}</tbody></table>`;
}
function collectGradingRows() {
  return [...document.querySelectorAll("#gradingSummary tbody tr")].map(tr => ({
    original_key: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
  }));
}
function applyGradingStatuses(rows) {
  const byKey = new Map(rows.map(row => [row.original_key, row]));
  for (const tr of document.querySelectorAll("#gradingSummary tbody tr")) {
    const row = byKey.get(tr.dataset.original);
    if (!row) continue;
    tr.querySelector(".row-percent").textContent = row.percent || "";
    tr.querySelector(".row-score").textContent = row.score || "";
    const cell = tr.querySelector(".row-status");
    cell.className = "row-status " + statusClass(row.status);
    const linkHtml = row.submission_url ? ` <a class="problem-link" href="${escapeHtml(row.submission_url)}" target="_blank" rel="noopener">Link</a>` : "";
    const msgHtml = row.message ? `<div class="test-meta">${escapeHtml(row.message)}</div>` : "";
    cell.innerHTML = `${escapeHtml(row.status || "")}${linkHtml}${msgHtml}`;
  }
}
document.getElementById("prepareGrading").onclick = async () => {
  const progressId = newProgressId();
  try {
    if (!selectedGradingZipFile) throw new Error("Hãy chọn file zip bài làm.");
    if (!selectedGradingCsvFile) throw new Error("Hãy chọn file CSV tài khoản.");
    status("running");
    log("Đang chuẩn bị dữ liệu chấm HNCode...");
    document.getElementById("downloadGradingResult").classList.add("hidden");
    startProgressPolling(progressId, "#gradingSummary", "grading");
    const form = new FormData();
    form.append("zip_file", selectedGradingZipFile);
    form.append("csv_file", selectedGradingCsvFile);
    form.append("contest_url", document.getElementById("gradingContestUrl").value.trim());
    form.append("progress_id", progressId);
    const res = await fetch("/api/prepare-hncode-grading", {method:"POST", body:form});
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.error || "Không chuẩn bị được dữ liệu chấm.");
    stopProgressPolling(progressId);
    preparedGrading = data.prepare_id;
    renderGradingTable(data.rows || []);
    document.getElementById("confirmGrading").disabled = false;
    log(data.log || "Đã chuẩn bị dữ liệu chấm.");
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("confirmGrading").onclick = async () => {
  const progressId = newProgressId();
  try {
    if (!preparedGrading) throw new Error("Hãy bấm Chuẩn bị dữ liệu trước.");
    status("running");
    log("Đang đăng nhập học sinh, tham gia contest và nộp bài...");
    markRowsProcessing("#gradingSummary", "Đang chấm...");
    startProgressPolling(progressId, "#gradingSummary", "grading");
    const data = await postJson("/api/confirm-hncode-grading", {
      prepare_id: preparedGrading,
      rows: collectGradingRows(),
      contest_password: document.getElementById("gradingContestPassword").value,
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    applyGradingStatuses(data.rows || []);
    const link = data.download_url ? `\nTải bảng điểm: ${location.origin}${data.download_url}` : "";
    log((data.log || "Đã chấm xong.") + link);
    if (data.download_url) {
      const a = document.getElementById("downloadGradingResult");
      a.href = data.download_url;
      a.classList.remove("hidden");
    }
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("chooseAiWarningZip").onclick = () => document.getElementById("aiWarningZipFile").click();
document.getElementById("aiWarningZipFile").addEventListener("change", event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("aiWarningZipName").value = file ? file.name : "";
});
document.getElementById("runAiWarning").onclick = async () => {
  try {
    status("running");
    log("Đang phân tích dấu hiệu sử dụng AI để code...");
    const input = document.getElementById("aiWarningZipFile");
    const file = input.files && input.files[0];
    const folder = document.getElementById("aiWarningFolder").value.trim();
    const form = new FormData();
    if (file) form.append("zip_file", file);
    else form.append("folder_path", folder);
    const res = await fetch("/api/misc/ai-code-warning", {method:"POST", body:form});
    if (!res.ok) {
      const data = await parseJsonResponse(res);
      throw new Error(data.error || "Không tạo được báo cáo.");
    }
    const summaryRaw = res.headers.get("X-AI-Warning-Summary") || "";
    const summary = summaryRaw ? JSON.parse(decodeURIComponent(summaryRaw)) : {};
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = summary.filename || "ai_code_warning_report.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    const text = `✓ Đã tạo báo cáo Excel cảnh báo AI code.\nSố contest zip: ${summary.zip_count || 0}\nSố file code: ${summary.code_file_count || 0}\nSố thí sinh: ${summary.student_count || 0}\nKhả năng cao: ${summary.high || 0}\nKhả năng trung bình: ${summary.medium || 0}\nKhả năng thấp: ${summary.low || 0}\nĐổi style cùng bài: ${summary.shift_count || 0}\nCặp nghi chép code: ${summary.copy_pair_count || 0}\nCặp rất giống: ${summary.copy_very_similar || 0}\nChi tiết cặp theo bài: ${summary.copy_detail_count || 0}\nThư mục code đã giải nén: ${summary.extracted_folder || ""}\nFile tải về: ${summary.filename || "ai_code_warning_report.xlsx"}`;
    document.getElementById("aiWarningSummary").innerHTML = `<div class="note">${escapeHtml(text).replaceAll("\n", "<br>")}</div>`;
    log(text);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

function contestTransferSettings() {
  return {
    reuse_existing_problems: document.getElementById("contestReuseExistingProblems").checked,
    create_missing_problems: document.getElementById("contestCreateMissingProblems").checked,
    time_limit: document.getElementById("contestProblemTime").value,
    memory_limit: document.getElementById("contestProblemMemory").value,
  };
}

function renderContestTransferTable(rows) {
  document.getElementById("contestTransferTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#contestTransferTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#contestTransferTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã contest</th><th>Tên contest</th><th>Thời gian</th><th>Bài trong contest</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_key)}">
      <td><input type="checkbox" class="row-selected" ${row.can_transfer ? "checked" : ""}></td>
      <td><input type="text" class="row-key" value="${escapeHtml(row.key)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name || "")}"></td>
      <td><div class="test-meta">${escapeHtml(row.start_time || "")}<br>${escapeHtml(row.end_time || "")}</div></td>
      <td>${renderContestProblemList(row.problems || [])}</td>
      <td class="row-status">${escapeHtml(row.status)}</td>
    </tr>`).join("")}</tbody></table>`;
}

function renderContestProblemList(problems) {
  if (!problems.length) return `<div class="test-meta">Không có bài.</div>`;
  return `<table class="inner-table"><thead><tr><th>Chọn</th><th>Mã bài</th><th>Điểm</th><th>Thứ tự</th><th>Trạng thái</th></tr></thead><tbody>
    ${problems.map(p => `<tr data-problem-code="${escapeHtml(p.code)}">
      <td><input type="checkbox" class="problem-selected" checked></td>
      <td>${escapeHtml(p.code)}</td>
      <td>${escapeHtml(p.points || "100")}</td>
      <td>${escapeHtml(p.order || "")}</td>
      <td>${escapeHtml(p.status || "")}</td>
    </tr>`).join("")}
  </tbody></table>`;
}

function collectContestRows() {
  return [...document.querySelectorAll("#contestTransferTable > table > tbody > tr")].map(tr => ({
    original_key: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    key: tr.querySelector(".row-key").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    problems: [...tr.querySelectorAll(".inner-table tbody tr")].map(pr => ({
      code: pr.dataset.problemCode,
      selected: pr.querySelector(".problem-selected").checked,
    })),
  }));
}

function applyContestStatuses(rows) {
  const byOriginal = new Map(rows.map(row => [row.original_key, row]));
  for (const tr of document.querySelectorAll("#contestTransferTable > table > tbody > tr")) {
    const row = byOriginal.get(tr.dataset.original);
    if (!row) continue;
    setStatusCell(tr.querySelector(".row-status"), row.status, row.link || "");
  }
}

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
function markRowsProcessing(selector, text="Đang xử lý...") {
  for (const tr of document.querySelectorAll(selector + " tbody tr")) {
    const selected = tr.querySelector(".row-selected");
    const statusCell = tr.querySelector(".row-status");
    if (selected && selected.checked && statusCell) {
      statusCell.className = "row-status";
      statusCell.textContent = text;
    }
  }
}
function applyStatuses(rows, selector) {
  const byOriginal = new Map(rows.map(row => [row.original_code, row]));
  for (const tr of document.querySelectorAll(selector + " tbody tr")) {
    const row = byOriginal.get(tr.dataset.original);
    if (!row) continue;
    setStatusCell(tr.querySelector(".row-status"), row.status, row.link || "");
  }
}
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[ch]));
}
