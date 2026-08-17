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
    <thead><tr><th>STT</th><th>Chọn</th><th>Mã contest</th><th>Tên contest</th><th>Thời gian</th><th>Bài trong contest</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map((row, index) => `<tr data-original="${escapeHtml(row.original_key)}">
      <td class="row-index">${index + 1}</td>
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
  return `<table class="inner-table"><thead><tr><th>STT</th><th>Chọn</th><th>Mã bài</th><th>Điểm</th><th>Thứ tự</th><th>Trạng thái</th></tr></thead><tbody>
    ${problems.map((p, index) => `<tr data-problem-code="${escapeHtml(p.code)}">
      <td class="row-index">${index + 1}</td>
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
