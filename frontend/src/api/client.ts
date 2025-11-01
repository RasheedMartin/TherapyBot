// api.ts
import axios from "axios";

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/api/`,
  withCredentials: true, // optional, for auth cookies
  headers: {
    "Content-Type": "application/json",
  },
});

export const setupInterceptors = (logout: () => void) => {
  // ✅ Attach access token to each request
  api.interceptors.request.use((config) => {
    const token = localStorage.getItem("access");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // ✅ Handle 401 responses automatically
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;

      // Avoid infinite loop
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        try {
          const refresh = localStorage.getItem("refresh");
          if (!refresh) throw new Error("No refresh token");

          // Attempt to refresh
          const res = await axios.post(
            `${import.meta.env.VITE_API_URL}/api/token/refresh/`,
            {
              refresh,
            }
          );

          const newAccess = res.data.access;
          localStorage.setItem("access", newAccess);

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${newAccess}`;
          return api(originalRequest);
        } catch (refreshError) {
          // If refresh fails → logout
          logout();
        }
      }

      return Promise.reject(error);
    }
  );
};

export default api;
