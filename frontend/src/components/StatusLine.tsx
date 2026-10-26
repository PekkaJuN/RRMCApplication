import { useEffect, useState } from "react";
import type { ApiResult } from "../api/client";
import { getHealth, type Health } from "../api/health";
import { fi } from "../i18n/fi";

const REFRESH_INTERVAL_MS = 30_000;

function statusTexts(result: ApiResult<Health>): string[] {
  if (!result.ok) {
    return [result.error.message];
  }
  const { checks, model_name: modelName } = result.data;
  const texts: string[] = [];
  if (checks.model === "unavailable") {
    texts.push(fi.status.ollamaUnreachable);
  } else if (checks.model === "missing_model") {
    texts.push(fi.status.modelMissing(modelName));
  }
  if (checks.ocr === "unavailable") {
    texts.push(fi.status.ocrUnavailable);
  }
  if (checks.folders === "unavailable") {
    texts.push(fi.status.foldersUnavailable);
  }
  if (checks.database === "unavailable") {
    texts.push(fi.status.databaseUnavailable);
  }
  return texts.length > 0 ? texts : [fi.status.allOk];
}

/** Shows the backend health, read on mount and every 30 seconds. */
export function StatusLine() {
  // Empty until the first answer arrives.
  const [texts, setTexts] = useState<string[]>([]);

  useEffect(() => {
    let isMounted = true;
    const refresh = () => {
      void getHealth().then((result) => {
        if (isMounted) {
          setTexts(statusTexts(result));
        }
      });
    };
    refresh();
    const interval = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div role="status" aria-label={fi.status.label}>
      {texts.length > 0 && (
        <ul>
          {texts.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
