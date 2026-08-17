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
    <thead><tr><th>STT</th><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Điểm</th><th>Dạng bài tập / Tags</th><th>Time</th><th>Memory</th><th>Điểm thành phần</th><th>Ghi đè</th><th>Up đề</th><th>Up test</th><th>Up lời giải</th><th>File test</th><th>Số test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map((row, index) => `<tr data-original="${escapeHtml(row.original_code)}" data-source-time="${escapeHtml(row.source_time_limit || row.time_limit || "1.0")}" data-source-memory="${escapeHtml(row.source_memory_limit || row.memory_limit || "1048576")}">
      <td class="row-index">${index + 1}</td>
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
      <td class="row-status ${statusClass(row.status)}">${escapeHtml(row.status || "Chưa up")}</td>
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
    <thead><tr><th>STT</th><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Điểm</th><th>Dạng bài tập / Tags</th><th>Time</th><th>Memory</th><th>Điểm thành phần</th><th>Up đề</th><th>Up test</th><th>Up lời giải</th><th>Test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map((row, index) => `<tr data-original="${escapeHtml(row.original_code)}">
      <td class="row-index">${index + 1}</td>
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
