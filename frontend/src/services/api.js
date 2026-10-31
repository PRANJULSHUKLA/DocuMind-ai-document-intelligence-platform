
import axios from "axios";
import { accessToken } from "./auth";

const configuredBaseUrl =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: configuredBaseUrl.replace(/\/+$/, ""),
  timeout: 120000,
  headers: {
    Accept: "application/json",
  },
});

api.interceptors.request.use(async (config) => {
  const token = await accessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new Event('documind:session-expired'));
    }
    if (error.code === "ECONNABORTED") {
      error.message =
        "The request timed out. The server may still be processing your document.";
    } else if (!error.response) {
      error.message =
        "Cannot connect to the backend. Check that FastAPI is running and VITE_API_BASE_URL is correct.";
    }

    return Promise.reject(error);
  }
);

export default api;
