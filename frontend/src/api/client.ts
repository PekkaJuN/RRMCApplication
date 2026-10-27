import { fi } from "../i18n/fi";

export interface ApiError {
  code: string;
  message: string;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

const BACKEND_UNREACHABLE: ApiError = { code: "network_error", message: fi.backendUnreachable };

function isApiError(body: unknown): body is { error: string; message: string } {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof body.error === "string" &&
    "message" in body &&
    typeof body.message === "string"
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    return undefined;
  }
}

/** GET a backend path. The response type is trusted to mirror the backend schema. */
export function apiGet<T>(path: string): Promise<ApiResult<T>> {
  return request<T>("GET", path);
}

/** POST a JSON body to a backend path. */
export function apiPost<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  return request<T>("POST", path, body);
}

/** PATCH a backend path with a JSON body. */
export function apiPatch<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  return request<T>("PATCH", path, body);
}

/** DELETE a backend path. Success has no data (204). */
export function apiDelete(path: string): Promise<ApiResult<undefined>> {
  return request<undefined>("DELETE", path);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  let response: Response;
  try {
    response = await fetch(new URL(path, window.location.origin), init);
  } catch {
    return { ok: false, error: BACKEND_UNREACHABLE };
  }
  const data = await readJson(response);
  if (response.ok) {
    return { ok: true, data: data as T };
  }
  // Without the backend's error format the answer came from the Vite proxy, which means
  // the backend did not answer.
  if (!isApiError(data)) {
    return { ok: false, error: BACKEND_UNREACHABLE };
  }
  return { ok: false, error: { code: data.error, message: data.message } };
}
