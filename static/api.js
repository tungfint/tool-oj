async function postJson(url, payload) {
  const res = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(apiErrorMessage(data));
  return data;
}
function apiErrorMessage(data) {
  if (!data) return "Request failed";
  if (data.error) return data.error;
  if (data.message) return data.message;
  if (Array.isArray(data.errors) && data.errors.length) {
    return data.errors.map(item => item.message || item.code || String(item)).join("; ");
  }
  return "Request failed";
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
  if (!res.ok) throw new Error(apiErrorMessage(data));
  return data;
}
async function prepareSingleUploadRequest(settings) {
  const form = new FormData();
  if (selectedSingleTestZipFile) form.append("test_zip", selectedSingleTestZipFile);
  form.append("payload", JSON.stringify(settings));
  const res = await fetch("/api/prepare-single-upload", {method:"POST", body:form});
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(apiErrorMessage(data));
  return data;
}
