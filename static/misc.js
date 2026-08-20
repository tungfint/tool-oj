function aiOptions() {
  return {
    target: document.getElementById("aiTarget").value,
    statement: document.getElementById("aiPartStatement").checked,
    metadata: document.getElementById("aiPartMetadata").checked,
    solution: document.getElementById("aiPartSolution").checked,
    test_review: document.getElementById("aiPartTestReview").checked,
  };
}
function syncAiSourceMode() {
  const mode = document.getElementById("aiSourceMode").value;
  document.getElementById("aiCodesBox").classList.toggle("hidden", mode !== "codes");
  document.getElementById("aiFileBox").classList.toggle("hidden", mode !== "file");
}
function syncAiProvider() {
  const provider = document.getElementById("aiProvider").value;
  document.getElementById("googleAiBox").classList.toggle("hidden", provider !== "google");
  document.getElementById("openRouterAiBox").classList.toggle("hidden", provider !== "openrouter");
}
function currentAiApiKey() {
  return document.getElementById("aiProvider").value === "openrouter"
    ? document.getElementById("openRouterApiKey").value.trim()
    : document.getElementById("aiApiKey").value.trim();
}
function currentAiModel() {
  return document.getElementById("aiProvider").value === "openrouter"
    ? document.getElementById("openRouterModel").value.trim()
    : document.getElementById("aiModel").value.trim();
}
const AI_TEXT = {
  selectAll: "Ch\u1ecdn t\u1ea5t c\u1ea3",
  unselectAll: "B\u1ecf ch\u1ecdn t\u1ea5t c\u1ea3",
  selected: "Ch\u1ecdn",
  code: "M\u00e3 b\u00e0i",
  name: "T\u00ean b\u00e0i",
  statement: "\u0110\u1ec1 b\u00e0i",
  status: "Tr\u1ea1ng th\u00e1i",
  result: "K\u1ebft qu\u1ea3",
  openMd: "M\u1edf md",
  saveKey: "\u0110\u00e3 l\u01b0u API key AI t\u1ea1m tr\u00ean tr\u00ecnh duy\u1ec7t m\u00e1y n\u00e0y.",
  fileRead: "\u0110\u00e3 \u0111\u1ecdc file.",
  preparing: "\u0110ang chu\u1ea9n b\u1ecb d\u1eef li\u1ec7u AI...",
  needApiKey: "H\u00e3y nh\u1eadp API key cho nh\u00e0 cung c\u1ea5p AI \u0111ang ch\u1ecdn.",
  callingAi: "\u0110ang g\u1ecdi AI...",
  callingAiLog: "\u0110ang g\u1ecdi AI \u0111\u1ec3 chu\u1ea9n h\u00f3a...",
  applying: "\u0110ang c\u1eadp nh\u1eadt web...",
  applyingLog: "\u0110ang c\u1eadp nh\u1eadt k\u1ebft qu\u1ea3 chu\u1ea9n h\u00f3a l\u00ean HNCode...",
  testReview: "Nh\u1eadn x\u00e9t test",
  issues: "V\u1ea5n \u0111\u1ec1 c\u1ea7n ki\u1ec3m tra",
  checks: "Ki\u1ec3m tra format",
};
function renderAiNormalizeTable(rows) {
  aiNormalizeRows = rows || [];
  document.getElementById("aiNormalizeTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#aiNormalizeTable', true)">${AI_TEXT.selectAll}</button>
    <button class="action" type="button" onclick="setRowSelection('#aiNormalizeTable', false)">${AI_TEXT.unselectAll}</button>
  </div><table>
    <thead><tr><th>STT</th><th>${AI_TEXT.selected}</th><th>${AI_TEXT.code}</th><th>${AI_TEXT.name}</th><th>${AI_TEXT.statement}</th><th>Solution</th><th>Point</th><th>${AI_TEXT.status}</th><th>${AI_TEXT.result}</th></tr></thead>
    <tbody>${aiNormalizeRows.map((row, index) => `<tr data-index="${index}" data-original="${escapeHtml(row.original_code || row.code || "")}">
      <td class="row-index">${index + 1}</td>
      <td><input type="checkbox" class="row-selected" ${row.can_normalize === false || row.selected === false ? "" : "checked"} ${row.can_normalize === false ? "disabled" : ""}></td>
      <td><input class="mini-input row-code" value="${escapeHtml(row.code || "")}"></td>
      <td><input class="mini-input row-name" value="${escapeHtml(row.name || "")}"></td>
      <td>${row.statement_link ? `<a href="${escapeHtml(row.statement_link)}" target="_blank" rel="noopener">${AI_TEXT.openMd}</a>` : ""}</td>
      <td>${row.solution_link ? `<a href="${escapeHtml(row.solution_link)}" target="_blank" rel="noopener">${AI_TEXT.openMd}</a>` : ""}</td>
      <td><input class="mini-input row-points" value="${escapeHtml(row.points || "")}"></td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}${row.link ? ` <a class="problem-link" href="${escapeHtml(row.link)}" target="_blank" rel="noopener">Link</a>` : ""}</td>
      <td><button class="action" type="button" onclick="selectAiResult(${index})">Xem</button>${row.link ? ` <a class="problem-link" href="${escapeHtml(row.link)}" target="_blank" rel="noopener">Link</a>` : ""}</td>
    </tr>`).join("")}</tbody></table>`;
}
function collectAiRows() {
  return [...document.querySelectorAll("#aiNormalizeTable tbody tr")].map(tr => {
    const row = aiNormalizeRows[Number(tr.dataset.index)] || {};
    return {
      ...row,
      selected: tr.querySelector(".row-selected").checked,
      code: tr.querySelector(".row-code")?.value.trim() || row.code || "",
      name: tr.querySelector(".row-name")?.value.trim() || row.name || "",
      points: tr.querySelector(".row-points")?.value.trim() || row.points || "",
    };
  });
}
function selectAiResult(index) {
  selectedAiResult = aiNormalizeRows[index] || null;
  document.getElementById("aiResultStatement").value = selectedAiResult?.statement_markdown || "";
  const details = [];
  if (selectedAiResult?.solution_markdown) details.push("## Solutions\n" + selectedAiResult.solution_markdown);
  if (selectedAiResult?.test_review) details.push(`## ${AI_TEXT.testReview}\n` + selectedAiResult.test_review);
  if (selectedAiResult?.issues?.length) details.push(`## ${AI_TEXT.issues}\n` + selectedAiResult.issues.map(item => "- " + item).join("\n"));
  if (selectedAiResult?.checks?.length) details.push(`## ${AI_TEXT.checks}\n` + selectedAiResult.checks.map(item => `${item.status} ${item.name}: ${item.message}`).join("\n"));
  document.getElementById("aiResultDetails").value = details.join("\n\n");
}
function applyAiRows(rows) {
  aiNormalizeRows = rows || [];
  renderAiNormalizeTable(aiNormalizeRows);
  if (aiNormalizeRows.length) selectAiResult(0);
}
document.getElementById("aiSourceMode").addEventListener("change", syncAiSourceMode);
syncAiSourceMode();
document.getElementById("aiProvider").addEventListener("change", syncAiProvider);
document.getElementById("aiHncodeUserMirror").value = accountFields.hncode_user.value || "hncode";
document.getElementById("saveAiKey").onclick = () => {
  localStorage.setItem("chuyenbai.ai_provider", document.getElementById("aiProvider").value);
  localStorage.setItem("chuyenbai.google_ai_key", document.getElementById("aiApiKey").value);
  localStorage.setItem("chuyenbai.google_ai_model", document.getElementById("aiModel").value);
  localStorage.setItem("chuyenbai.openrouter_ai_key", document.getElementById("openRouterApiKey").value);
  localStorage.setItem("chuyenbai.openrouter_ai_model", document.getElementById("openRouterModel").value);
  append(AI_TEXT.saveKey);
};
document.getElementById("aiProvider").value = localStorage.getItem("chuyenbai.ai_provider") || document.getElementById("aiProvider").value;
document.getElementById("aiApiKey").value = localStorage.getItem("chuyenbai.google_ai_key") || "";
document.getElementById("aiModel").value = localStorage.getItem("chuyenbai.google_ai_model") || document.getElementById("aiModel").value;
if (!document.getElementById("aiModel").value || document.getElementById("aiModel").value.startsWith("gemini-2.")) {
  document.getElementById("aiModel").value = "gemini-3.5-flash";
}
document.getElementById("openRouterApiKey").value = localStorage.getItem("chuyenbai.openrouter_ai_key") || "";
document.getElementById("openRouterModel").value = localStorage.getItem("chuyenbai.openrouter_ai_model") || document.getElementById("openRouterModel").value || "deepseek/deepseek-v4-flash-0731";
syncAiProvider();
document.getElementById("chooseAiSourceFile").onclick = () => document.getElementById("aiSourceFile").click();
document.getElementById("aiSourceFile").addEventListener("change", async event => {
  selectedAiSourceFile = event.target.files && event.target.files[0] || null;
  document.getElementById("aiSourceFileName").value = selectedAiSourceFile ? selectedAiSourceFile.name : "";
  if (!selectedAiSourceFile) return;
  try {
    status("running");
    const form = new FormData();
    form.append("source_file", selectedAiSourceFile);
    const res = await fetch("/api/ai/prepare-file", {method:"POST", body:form});
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(apiErrorMessage(data));
    document.getElementById("aiSourceText").value = data.source_text || "";
    aiSourceFileBase64 = data.file_base64 || "";
    aiSourceFileMimeType = data.mime_type || "";
    append(data.message || AI_TEXT.fileRead);
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
});
async function prepareAiNormalizeFlow() {
  status("running");
  saveAccounts();
  document.getElementById("aiHncodeUserMirror").value = accountFields.hncode_user.value || "hncode";
  const sourceMode = document.getElementById("aiSourceMode").value;
  log(AI_TEXT.preparing);
  const payload = {
    source_mode: sourceMode,
    target: document.getElementById("aiTarget").value,
    codes: document.getElementById("aiProblemCodes").value,
    source_text: document.getElementById("aiSourceText").value,
    filename: document.getElementById("aiSourceFileName").value,
    problem_code: document.getElementById("aiFileCode").value.trim(),
    problem_name: document.getElementById("aiFileName").value.trim(),
    points: document.getElementById("aiFilePoints").value.trim() || "100",
    tags: document.getElementById("aiFileTags").value.trim(),
    file_base64: aiSourceFileBase64,
    mime_type: aiSourceFileMimeType,
    account: accountPayload("hncode"),
  };
  const data = await postJson("/api/ai/prepare-normalize", payload);
  preparedAiNormalize = data.prepare_id;
  renderAiNormalizeTable(data.rows || []);
  document.getElementById("runAiNormalize").disabled = false;
  log(data.log);
  status("ready", "ok");
  return data;
}
async function waitForAiNormalizeJob(jobId) {
  let failedPolls = 0;
  while (true) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    try {
      const res = await fetch(`/api/progress/${jobId}`, {cache: "no-store"});
      const data = await parseJsonResponse(res);
      if (!res.ok) throw new Error(apiErrorMessage(data));
      failedPolls = 0;
      if (data.rows && data.rows.length) applyAiRows(data.rows);
      if (data.log) log(data.log);
      else if (data.message || data.total) log(progressMessage(data));
      status(data.finished ? (data.ok ? "done" : "failed") : `${data.done || 0}/${data.total || 0}`, data.finished ? (data.ok ? "ok" : "err") : "");
      if (data.finished) return data;
    } catch (err) {
      failedPolls += 1;
      if (failedPolls >= 6) throw err;
    }
  }
}
async function runAiNormalizeFlow() {
  if (!preparedAiNormalize) await prepareAiNormalizeFlow();
  if (!currentAiApiKey()) throw new Error(AI_TEXT.needApiKey);
  status("running");
  markRowsProcessing("#aiNormalizeTable", AI_TEXT.callingAi);
  log(AI_TEXT.callingAiLog);
  const started = await postJson("/api/ai/normalize-start", {
    prepare_id: preparedAiNormalize,
    provider: document.getElementById("aiProvider").value,
    api_key: currentAiApiKey(),
    model: currentAiModel(),
    options: aiOptions(),
    rows: collectAiRows(),
  });
  const data = await waitForAiNormalizeJob(started.job_id);
  applyAiRows(data.rows || []);
  log(data.log || data.message);
  status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  return data;
}
async function applyAiNormalizeFlow() {
  if (!preparedAiNormalize) await prepareAiNormalizeFlow();
  if (!aiNormalizeRows.some(row => row.statement_markdown)) await runAiNormalizeFlow();
  status("running");
  markRowsProcessing("#aiNormalizeTable", AI_TEXT.applying);
  log(AI_TEXT.applyingLog);
  const data = await postJson("/api/ai/apply-normalize", {
    prepare_id: preparedAiNormalize,
    target: document.getElementById("aiTarget").value,
    options: aiOptions(),
    rows: collectAiRows(),
    account: accountPayload("hncode"),
  });
  applyAiRows(data.rows || []);
  log(data.log);
  status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  return data;
}
document.getElementById("prepareAiNormalize").onclick = async () => {
  try { await prepareAiNormalizeFlow(); }
  catch (err) {
    preparedAiNormalize = null;
    document.getElementById("runAiNormalize").disabled = true;
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("runAiNormalize").onclick = async () => {
  try { await runAiNormalizeFlow(); }
  catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("applyAiNormalize").onclick = async () => {
  try { await applyAiNormalizeFlow(); }
  catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("validateAiStatement").onclick = async () => {
  try {
    const data = await postJson("/api/ai/validate-statement", {target: document.getElementById("aiTarget").value, markdown: document.getElementById("aiResultStatement").value});
    document.getElementById("aiResultDetails").value = (data.rows || []).map(row => `${row.status} ${row.name}: ${row.message}`).join("\n");
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("sendAiToSingleUpload").onclick = () => {
  const statement = document.getElementById("aiResultStatement").value.trim();
  if (!statement) {
    log("Chưa có Markdown AI để đưa sang Up 1 bài.");
    status("failed", "err");
    return;
  }
  const row = selectedAiResult || {};
  document.querySelector('[data-panel="single-upload"]').click();
  document.getElementById("singleUploadTarget").value = document.getElementById("aiTarget").value;
  document.getElementById("singleCode").value = row.code || "";
  document.getElementById("singleName").value = row.name || "";
  document.getElementById("singlePoints").value = row.points || "100";
  document.getElementById("singleTags").value = row.tags || "";
  document.getElementById("singleStatement").value = statement;
  document.getElementById("singleSolution").value = row.solution_markdown || "";
  append("Đã đưa đề AI sang Up 1 bài. Hãy kiểm tra lại rồi bấm Chuẩn bị dữ liệu.");
};

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
    document.getElementById("codeListLinksOutput").value = data.links_text || data.source_links_text || "";
    const rows = data.rows || [];
    const groupCount = data.meta && data.meta.group_count || 1;
    document.getElementById("codeListSummary").innerHTML = `<div class="note">Tìm thấy ${rows.length} bài từ ${groupCount} nguồn.</div>
      <table>
        <thead><tr><th>Nguồn</th><th>STT</th><th>Mã bài</th><th>Tên bài</th><th>Điểm</th><th>Link</th><th>Link trong contest</th></tr></thead>
        <tbody>${rows.map(row => `<tr>
          <td>${escapeHtml(row.source_label || "")}</td>
          <td>${row.index || row.order || ""}</td>
          <td>${row.link ? `<a href="${escapeHtml(row.link)}" target="_blank" rel="noopener"><code>${escapeHtml(row.code || "")}</code></a>` : `<code>${escapeHtml(row.code || "")}</code>`}</td>
          <td>${escapeHtml(row.title || "")}</td>
          <td>${escapeHtml(row.points || row.score || "")}</td>
          <td>${row.link ? `<a href="${escapeHtml(row.link)}" target="_blank" rel="noopener">Link</a>` : ""}</td>
          <td>${row.source_link ? `<a href="${escapeHtml(row.source_link)}" target="_blank" rel="noopener">Link</a>` : ""}</td>
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

document.getElementById("fillStatementExportFromCodeList").onclick = () => {
  const codes = document.getElementById("codeListOutput").value.trim();
  const links = document.getElementById("codeListLinksOutput").value.trim();
  document.getElementById("statementExportItems").value = codes || links;
};
document.getElementById("runStatementExport").onclick = async () => {
  try {
    status("running");
    saveAccounts();
    log("Đang xuất đề bài HNCode ra Markdown...");
    const data = await postJson("/api/misc/export-hncode-statements", {
      items: document.getElementById("statementExportItems").value,
      account: accountPayload("hncode"),
    });
    const rows = data.rows || [];
    const downloadHtml = data.download_url
      ? `<a class="action primary" href="${escapeHtml(data.download_url)}" target="_blank" rel="noopener" download="hncode_statements.md">Tải file Markdown</a>`
      : "";
    document.getElementById("statementExportSummary").innerHTML = `<div class="note">${escapeHtml(data.message || "")}</div>
      <div class="actions">${downloadHtml}</div>
      <table>
        <thead><tr><th>STT</th><th>Mã bài</th><th>Tên bài</th><th>Trạng thái</th><th>Link</th></tr></thead>
        <tbody>${rows.map(row => `<tr>
          <td>${row.index || ""}</td>
          <td><code>${escapeHtml(row.code || "")}</code></td>
          <td>${escapeHtml(row.name || "")}</td>
          <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}</td>
          <td>${row.link ? `<a href="${escapeHtml(row.link)}" target="_blank" rel="noopener">Link</a>` : ""}</td>
        </tr>`).join("")}</tbody>
      </table>`;
    log(data.log || data.message || "Đã xuất file Markdown.");
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

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
document.getElementById("gradingMode").addEventListener("change", event => {
  document.getElementById("gradingPollSeconds").disabled = event.target.value === "submit_only";
});
document.getElementById("gradingPollSeconds").disabled = document.getElementById("gradingMode").value === "submit_only";
function renderGradingTable(rows) {
  document.getElementById("gradingSummary").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#gradingSummary', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#gradingSummary', false)">Bỏ chọn tất cả</button>
    <button class="action" type="button" onclick="selectGradingErrorRows()">Chọn dòng lỗi</button>
    <button class="action" type="button" onclick="sortGradingErrorRowsTop()">Đưa lỗi lên trên</button>
    <button class="action primary" type="button" onclick="selectAndSortGradingErrors()">Chọn lỗi & đưa lên trên</button>
  </div><table>
    <thead><tr><th>STT</th><th>Chọn</th><th>Folder</th><th>Học sinh</th><th>Tài khoản chấm</th><th>Mã bài</th><th>Tên bài</th><th>Điểm bài</th><th>File</th><th>%</th><th>Điểm</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map((row, index) => `<tr data-original="${escapeHtml(row.original_key)}">
      <td class="row-index">${index + 1}</td>
      <td><input type="checkbox" class="row-selected" ${row.selected ? "checked" : ""}></td>
      <td>${escapeHtml(row.folder || "")}</td>
      <td>${escapeHtml(row.student || "")}</td>
      <td><input class="grading-username compact-input" type="text" value="${escapeHtml(row.username || "")}" title="Tài khoản chấm tương ứng folder này"></td>
      <td>${escapeHtml(row.problem || "")}</td>
      <td>${escapeHtml(row.problem_title || "")}</td>
      <td>${escapeHtml(row.contest_points || "")}</td>
      <td><div class="test-meta">${escapeHtml(row.relative_path || row.file || "")}</div></td>
      <td class="row-percent">${escapeHtml(row.percent || "")}</td>
      <td class="row-score">${escapeHtml(row.score || "")}</td>
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "")}${row.submission_url ? ` <a class="problem-link" href="${escapeHtml(row.submission_url)}" target="_blank" rel="noopener">Link</a>` : ""}${row.message ? `<div class="test-meta">${escapeHtml(row.message)}</div>` : ""}</td>
    </tr>`).join("")}</tbody></table>`;
}
function isGradingErrorRow(tr) {
  const text = tr.querySelector(".row-status")?.textContent || "";
  return text.includes("✗") || text.includes("Lỗi") || text.includes("HTTP 429");
}
function selectGradingErrorRows() {
  const rows = [...document.querySelectorAll("#gradingSummary tbody tr")];
  rows.forEach(tr => {
    const checkbox = tr.querySelector(".row-selected");
    if (checkbox) checkbox.checked = isGradingErrorRow(tr);
  });
}
function sortGradingErrorRowsTop() {
  const tbody = document.querySelector("#gradingSummary tbody");
  if (!tbody) return;
  [...tbody.querySelectorAll("tr")]
    .sort((left, right) => Number(isGradingErrorRow(right)) - Number(isGradingErrorRow(left)))
    .forEach(tr => tbody.appendChild(tr));
}
function selectAndSortGradingErrors() {
  selectGradingErrorRows();
  sortGradingErrorRowsTop();
}
function collectGradingRows() {
  return [...document.querySelectorAll("#gradingSummary tbody tr")].map(tr => ({
    original_key: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    username: tr.querySelector(".grading-username")?.value.trim() || "",
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
    form.append("problem_file_mapping", document.getElementById("gradingProblemFileMapping").value);
    form.append("progress_id", progressId);
    const res = await fetch("/api/prepare-hncode-grading", {method:"POST", body:form});
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.error || "Không chuẩn bị được dữ liệu chấm.");
    stopProgressPolling(progressId);
    preparedGrading = data.prepare_id;
    if (data.meta && data.meta.problem_file_mapping) {
      document.getElementById("gradingProblemFileMapping").value = data.meta.problem_file_mapping;
    }
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
    const mode = document.getElementById("gradingMode").value;
    const submitOnly = mode === "submit_only";
    status("running");
    log(submitOnly ? "Đang đăng nhập học sinh, tham gia contest và nộp bài song song..." : "Đang đăng nhập học sinh, tham gia contest, nộp bài và chờ kết quả...");
    markRowsProcessing("#gradingSummary", submitOnly ? "Đang nộp..." : "Đang chấm...");
    startProgressPolling(progressId, "#gradingSummary", "grading");
    const data = await postJson("/api/confirm-hncode-grading", {
      prepare_id: preparedGrading,
      rows: collectGradingRows(),
      contest_password: document.getElementById("gradingContestPassword").value,
      mode,
      wait_seconds: document.getElementById("gradingPollSeconds").value,
      max_workers: document.getElementById("gradingWorkers").value,
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    applyGradingStatuses(data.rows || []);
    sortGradingErrorRowsTop();
    const downloadUrl = data.download_url ? appPath(data.download_url) : "";
    const link = downloadUrl ? `\nTải bảng điểm: ${location.origin}${downloadUrl}` : "";
    log((data.log || (submitOnly ? "Đã nộp xong." : "Đã chấm xong.")) + link);
    if (data.download_url) {
      const a = document.getElementById("downloadGradingResult");
      a.href = downloadUrl;
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
