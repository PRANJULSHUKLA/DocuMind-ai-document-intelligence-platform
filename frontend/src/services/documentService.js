
import api from "./api";

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  // Do not manually set Content-Type. The browser must add the multipart boundary.
  const response = await api.post("/upload", formData);
  return response.data;
}

export async function getDocumentStatus(fileId) {
  const response = await api.get(
    `/status/${encodeURIComponent(fileId)}`
  );
  return response.data;
}

export async function getDocuments() {
  const response = await api.get("/files");
  return response.data;
}

export async function getDocument(fileId) {
  const response = await api.get(
    `/files/${encodeURIComponent(fileId)}`
  );
  return response.data;
}

export async function analyzeDocument(
  fileId,
  analysisType = "contract"
) {
  const response = await api.post("/analyze", {
    file_id: fileId,
    analysis_type: analysisType,
  });

  return response.data;
}

export async function generateWorkflow(fileId, objective) {
  const response = await api.post("/workflow", {
    file_id: fileId,
    objective,
  });

  return response.data;
}

export async function askDocument(fileId, question) {
  const response = await api.post("/chat", {
    file_id: fileId,
    question,
  });

  return response.data;
}

export default api;
