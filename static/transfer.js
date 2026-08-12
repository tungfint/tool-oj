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
