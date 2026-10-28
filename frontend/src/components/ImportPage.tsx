import { useEffect, useRef, useState } from "react";
import type { ApiResult } from "../api/client";
import { getImport, startImport, type ImportState } from "../api/imports";
import { fi } from "../i18n/fi";

const POLL_INTERVAL_MS = 1000;

/** The Tuonti page: start an import and see its progress and report. */
export function ImportPage() {
  const [state, setState] = useState<ImportState | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Counts answers while running, so every answer (also a failed one) schedules the next poll.
  const [polls, setPolls] = useState(0);
  // A start answers with a newer state than the first request, which may arrive later.
  const hasStarted = useRef(false);
  const isRunning = state?.state === "running";

  function show(result: ApiResult<ImportState>) {
    if (result.ok) {
      setState(result.data);
    } else {
      setError(result.error.message);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void getImport().then((result) => {
      if (!cancelled && !hasStarted.current) {
        show(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isRunning) {
      return;
    }
    let cancelled = false;
    // The next request waits for the previous answer, so requests never overlap.
    const timer = setTimeout(() => {
      void getImport().then((result) => {
        if (!cancelled) {
          show(result);
          setPolls((count) => count + 1);
        }
      });
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [isRunning, polls]);

  async function start() {
    const result = await startImport();
    if (result.ok) {
      hasStarted.current = true;
      setError(null);
    }
    show(result);
  }

  return (
    <section aria-labelledby="import-heading">
      <h2 id="import-heading">{fi.import.heading}</h2>
      <p>{fi.import.instruction}</p>
      <button type="button" disabled={isRunning} onClick={() => void start()}>
        {fi.import.start}
      </button>
      {error && <p role="alert">{error}</p>}
      {state?.state === "idle" && <p>{fi.import.notRunYet}</p>}
      {isRunning && <p>{fi.import.progress(state.processed, state.total)}</p>}
      {state?.state === "finished" && <Report state={state} />}
    </section>
  );
}

function Report({ state }: { state: ImportState }) {
  return (
    <section aria-labelledby="import-report-heading">
      <h3 id="import-report-heading">{fi.import.reportHeading}</h3>
      {state.total === 0 ? (
        <p>{fi.import.nothingToImport}</p>
      ) : (
        <>
          <p>{fi.import.imported(state.imported)}</p>
          <p>{fi.import.duplicates(state.duplicates.length)}</p>
          <p>{fi.import.failed(state.failures.length)}</p>
          {state.duplicates.length > 0 && (
            <>
              <h4 id="import-duplicates-heading">{fi.import.duplicatesHeading}</h4>
              <ul aria-labelledby="import-duplicates-heading">
                {state.duplicates.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </>
          )}
          {state.failures.length > 0 && (
            <>
              <h4 id="import-failures-heading">{fi.import.failuresHeading}</h4>
              <ul aria-labelledby="import-failures-heading">
                {state.failures.map((failure) => (
                  <li key={failure.file_name}>
                    <span>{failure.file_name}</span>: {failure.message}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
