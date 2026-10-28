import type { ImportState } from "../api/imports";

/** The state before the first run. */
export const IDLE: ImportState = {
  state: "idle",
  total: 0,
  processed: 0,
  imported: 0,
  duplicates: [],
  failures: [],
  started_at: null,
  finished_at: null,
};

/** A running state with `processed` of `total` files handled. */
export function running(processed: number, total: number): ImportState {
  return {
    ...IDLE,
    state: "running",
    total,
    processed,
    imported: processed,
    started_at: "2026-10-28T10:00:00Z",
  };
}

/** The finished run of the spec's Run state example. */
export const FINISHED: ImportState = {
  state: "finished",
  total: 4,
  processed: 4,
  imported: 1,
  duplicates: ["b.jpg"],
  failures: [
    {
      file_name: "notes.txt",
      reason: "unsupported_format",
      message: "Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.",
    },
  ],
  started_at: "2026-10-28T10:00:00Z",
  finished_at: "2026-10-28T10:00:02Z",
};
