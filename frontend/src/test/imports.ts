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
  stopped: null,
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
  stopped: null,
};

/** A run stopped by the model after one of three files (receipt-reading AC20). */
export const STOPPED: ImportState = {
  ...FINISHED,
  total: 3,
  processed: 1,
  imported: 1,
  duplicates: [],
  failures: [],
  stopped: {
    reason: "model_unavailable",
    message:
      "Kielimalli ei vastaa. Tuonti pysäytettiin; jäljellä olevat kuvat jäivät tuontikansioon.",
  },
};

/** One failure of each reason added by the receipt-reading spec. */
export const READ_FAILURES: ImportState = {
  ...FINISHED,
  total: 4,
  processed: 4,
  imported: 0,
  duplicates: [],
  failures: [
    { file_name: "a.jpg", reason: "unreadable_image", message: "Kuvaa ei voitu avata." },
    { file_name: "b.jpg", reason: "ocr_failed", message: "Tekstin tunnistus epäonnistui." },
    { file_name: "c.jpg", reason: "no_text", message: "Kuvasta ei löytynyt tekstiä." },
    { file_name: "d.jpg", reason: "parse_failed", message: "Kuittia ei voitu tulkita." },
  ],
};
