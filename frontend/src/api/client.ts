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
export async function apiGet<T>(path: string): Promise<ApiResult<T>> {
  let response: Response;
  try {
    response = await fetch(new URL(path, window.location.origin));
  } catch {
    return { ok: false, error: BACKEND_UNREACHABLE };
  }
  const body = await readJson(response);
  if (response.ok) {
    return { ok: true, data: body as T };
  }
  // Without the backend's error format the answer came from the Vite proxy, which means
  // the backend did not answer.
  if (!isApiError(body)) {
    return { ok: false, error: BACKEND_UNREACHABLE };
  }
  return { ok: false, error: { code: body.error, message: body.message } };
}
