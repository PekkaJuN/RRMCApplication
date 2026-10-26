import { apiGet, type ApiResult } from "./client";

/** Mirrors the backend schema of GET /api/health. */
export interface Health {
  status: "ok" | "degraded";
  model_name: string;
  checks: {
    database: "ok" | "unavailable";
    folders: "ok" | "unavailable";
    ocr: "ok" | "unavailable";
    model: "ok" | "unavailable" | "missing_model";
  };
}

export function getHealth(): Promise<ApiResult<Health>> {
  return apiGet<Health>("/api/health");
}
