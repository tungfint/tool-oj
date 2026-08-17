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
    <thead><tr><th>STT</th><th>Chọn</th><th>Thứ tự nguồn</th><th>Mã bài</th><th>Tên bài</th><th>Điểm lesson</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map((row, index) => `<tr data-code="${escapeHtml(row.code)}">
      <td class="row-index">${index + 1}</td>
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
    <thead><tr><th>STT</th><th>Chọn</th><th>Loại</th><th>Thứ tự</th><th>Mã/ID nguồn</th><th>Tên</th><th>Mã contest đích</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map((row, index) => `<tr data-kind="${escapeHtml(row.kind)}" data-key="${escapeHtml(row.key)}">
      <td class="row-index">${index + 1}</td>
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
