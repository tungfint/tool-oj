function newProgressId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID().replaceAll("-", "");
  return Array.from({length: 32}, () => Math.floor(Math.random() * 16).toString(16)).join("");
}
function statusClass(text) {
  const value = String(text || "");
  if (value.startsWith("✓") || value.includes("Thành công") || value.includes("Đã đọc")) return "ok";
  if (value.includes("⚠") || value.includes("đã tồn tại") || value.includes("Đã tồn tại") || value.includes("đã có") || value.includes("Đã có")) return "warn";
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
