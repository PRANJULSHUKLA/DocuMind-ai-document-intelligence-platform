
import axios from "axios";

const configuredBaseUrl =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: configuredBaseUrl.replace(/\/+$/, ""),
  timeout: 120000,
  headers: {
    Accept: "application/json",
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
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
