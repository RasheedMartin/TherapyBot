import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

export const API_ROOT = `${(import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "")}/api/`;

const api = axios.create({
  baseURL: API_ROOT,
  headers: { "Content-Type": "application/json" },
  timeout: 90_000,
});

// --- Token storage ----------------------------------------------------------
// "Remember me" keeps tokens in localStorage; otherwise they live for the tab session.

const ACCESS = "access";
const REFRESH = "refresh";

const storageWithTokens = (): Storage | null => {
  try {
    if (localStorage.getItem(REFRESH)) return localStorage;
    if (sessionStorage.getItem(REFRESH)) return sessionStorage;
  } catch {
    // storage unavailable (private mode etc.)
  }
  return null;
};

export const tokens = {
  access: () => storageWithTokens()?.getItem(ACCESS) ?? null,
  refresh: () => storageWithTokens()?.getItem(REFRESH) ?? null,
  set(access: string, refresh: string, remember?: boolean) {
    const target =
      remember === undefined
        ? (storageWithTokens() ?? localStorage)
        : remember
          ? localStorage
          : sessionStorage;
    tokens.clear();
    target.setItem(ACCESS, access);
    target.setItem(REFRESH, refresh);
  },
  clear() {
    for (const s of [localStorage, sessionStorage]) {
      s.removeItem(ACCESS);
      s.removeItem(REFRESH);
    }
  },
};

// --- Interceptors -----------------------------------------------------------

let onSessionExpired: () => void = () => {};
export const setSessionExpiredHandler = (fn: () => void) => {
  onSessionExpired = fn;
};
export const expireSession = () => {
  tokens.clear();
  onSessionExpired();
};

api.interceptors.request.use((config) => {
  const token = tokens.access();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Share one refresh request between concurrent 401s
let refreshing: Promise<string> | null = null;

export const refreshAccessToken = async (): Promise<string> => {
  const refresh = tokens.refresh();
  if (!refresh) throw new Error("No refresh token");
  const res = await axios.post(`${API_ROOT}token/refresh/`, { refresh });
  tokens.set(res.data.access, res.data.refresh ?? refresh);
  return res.data.access;
};

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const isAuthEndpoint = original?.url?.startsWith("token/");

    if (error.response?.status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        refreshing ??= refreshAccessToken().finally(() => {
          refreshing = null;
        });
        const access = await refreshing;
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch {
        tokens.clear();
        onSessionExpired();
      }
    }
    return Promise.reject(error);
  },
);

// --- Errors -----------------------------------------------------------------

/** An error whose message is already safe to show the user. */
export class UserFacingError extends Error {}

/** Turn a DRF error response into a single human-readable message. */
export const getErrorMessage = (err: unknown, fallback = "Something went wrong. Please try again."): string => {
  if (err instanceof UserFacingError) return err.message;
  if (err instanceof TypeError) return "Can't reach the server. Check your connection and try again.";
  if (!(err instanceof AxiosError)) return fallback;
  if (!err.response) {
    return err.code === "ECONNABORTED"
      ? "The request timed out. Please try again."
      : "Can't reach the server. Check your connection and try again.";
  }
  if (err.response.status === 429) return "You're going a little fast. Please wait a moment and try again.";

  const data = err.response.data as unknown;
  if (typeof data === "string") return fallback;
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    const first = Object.values(record).flat()[0];
    if (typeof first === "string") return first;
  }
  return fallback;
};

/** Field-level errors from a DRF 400 response, keyed by field name. */
export const getFieldErrors = (err: unknown): Record<string, string> => {
  if (!(err instanceof AxiosError) || err.response?.status !== 400) return {};
  const data = err.response.data as Record<string, unknown>;
  if (!data || typeof data !== "object") return {};
  return Object.fromEntries(
    Object.entries(data)
      .filter(([key]) => key !== "detail" && key !== "non_field_errors")
      .map(([key, value]) => [key, Array.isArray(value) ? value.join(" ") : String(value)]),
  );
};

export default api;
