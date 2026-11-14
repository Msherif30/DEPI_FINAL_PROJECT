const TOKEN_KEY = "rm_token";
const USER_KEY = "rm_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getStoredUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function setStoredUser(user: unknown | null) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (typeof err.detail === "string") return err.detail;
    if (err.detail && typeof err.detail === "object") {
      const d = err.detail as Record<string, unknown>;
      if (typeof d.message === "string") return d.message;
      if (Array.isArray(d.detail)) {
        return d.detail
          .map((row) => (row && typeof row === "object" ? String((row as { msg?: string }).msg ?? "") : String(row)))
          .join(", ");
      }
      return JSON.stringify(err.detail);
    }
    return `Request failed (${err.status})`;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}

type Options = Omit<RequestInit, "body"> & { body?: unknown; rawBody?: BodyInit };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { body, rawBody, headers, ...rest } = options;
  const finalHeaders = new Headers(headers);
  const token = getToken();
  if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  let payload: BodyInit | undefined = rawBody;
  if (body !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }
  const response = await fetch(`/api${path}`, { ...rest, headers: finalHeaders, body: payload });
  if (response.status === 401) {
    setToken(null);
    setStoredUser(null);
    window.dispatchEvent(new CustomEvent("rm:unauthorized"));
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail ?? data;
    } catch {
      /* ignore */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
