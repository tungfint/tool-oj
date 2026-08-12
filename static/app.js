const TARGETS = window.APP_CONFIG.targets;
let preparedUpload = null;
let preparedSingleUpload = null;
let preparedTransfer = null;
let preparedContestTransfer = null;
let preparedQuiz = null;
let preparedContestLessonCopy = null;
let preparedCourseClone = null;
let preparedGrading = null;
let preparedAiNormalize = null;
let selectedZipFile = null;
let selectedSingleTestZipFile = null;
let selectedGradingZipFile = null;
let selectedGradingCsvFile = null;
let selectedAiSourceFile = null;
let aiNormalizeRows = [];
let selectedAiResult = null;
let aiSourceFileBase64 = "";
let aiSourceFileMimeType = "";
const QUIZ_FORMAT_GUIDE = window.APP_CONFIG.quizFormatGuide;

const logEl = document.getElementById("log");
const statusEl = document.getElementById("jobStatus");
let logText = "Sẵn sàng.";
const progressTimers = new Map();
function setupSecretToggles() {
  for (const input of document.querySelectorAll("input.secret-input, input[type='password']")) {
    if (input.dataset.eyeReady) continue;
    input.dataset.eyeReady = "1";
    const wrap = document.createElement("div");
    wrap.className = "secret-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "eye-btn";
    button.title = "An / hien";
    button.textContent = "\u{1F441}";
    button.addEventListener("click", () => {
      input.type = input.type === "password" ? "text" : "password";
    });
    wrap.appendChild(button);
  }
}
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
setupSecretToggles();

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
