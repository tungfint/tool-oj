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
