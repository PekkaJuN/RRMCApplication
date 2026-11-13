import { useEffect, useState, type MouseEvent } from "react";
import {
  archiveYear,
  deleteArchivedYear,
  getArchive,
  type ArchiveCandidate,
  type ArchivedYear,
  type ArchiveOverview,
} from "../api/archive";
import { fi } from "../i18n/fi";
import { isPlainLeftClick, PAGE_PATHS } from "../navigation";

interface Props {
  onOpenYear: (year: number) => void;
}

/** Which confirmation is open, if any. */
type Asking = { kind: "archive" | "delete"; year: number } | null;

/** What the last finished request reports. */
interface Report {
  text: string;
  notMoved: string[];
}

/** The Arkisto page (archiving PC14): archive finished years and manage archived ones. */
export function ArchivePage({ onOpenYear }: Props) {
  const [overview, setOverview] = useState<ArchiveOverview | null>(null);
  const [asking, setAsking] = useState<Asking>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Counts reloads, so the lists are read again after every request (AC37).
  const [loads, setLoads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getArchive().then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setOverview(result.data);
      } else {
        setError(result.error.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loads]);

  async function run(kind: "archive" | "delete", year: number) {
    // The state update is not seen by a second click in the same tick, so the button's
    // disabled state alone does not stop a double click (AC36).
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    setError(null);
    setReport(null);
    if (kind === "archive") {
      const result = await archiveYear(year);
      if (result.ok) {
        const { receipts, lines, images_not_moved } = result.data;
        setReport({
          text: fi.archive.archived(year, receipts, lines),
          notMoved: images_not_moved,
        });
      } else {
        setError(result.error.message);
      }
    } else {
      const result = await deleteArchivedYear(year);
      if (result.ok) {
        setReport({ text: fi.archive.deleted(year), notMoved: [] });
      } else {
        setError(result.error.message);
      }
    }
    setIsBusy(false);
    setAsking(null);
    setLoads((count) => count + 1);
  }

  function open(event: MouseEvent<HTMLAnchorElement>, year: number) {
    if (!isPlainLeftClick(event)) {
      return;
    }
    event.preventDefault();
    onOpenYear(year);
  }

  function confirmation(kind: "archive" | "delete", year: number, text: string) {
    const label = kind === "archive" ? fi.archive.archive : fi.archive.delete;
    return (
      <p className="confirm-delete">
        {text}{" "}
        <button type="button" disabled={isBusy} onClick={() => void run(kind, year)}>
          {label}
        </button>{" "}
        <button type="button" disabled={isBusy} onClick={() => setAsking(null)}>
          {fi.actions.cancel}
        </button>
      </p>
    );
  }

  function candidateItem(candidate: ArchiveCandidate) {
    const { year, receipts, lines, images, unreviewed } = candidate;
    const isAsking = asking?.kind === "archive" && asking.year === year;
    return (
      <li key={year}>
        {year}: {fi.archive.candidate(receipts, lines, images)}{" "}
        {unreviewed > 0 ? (
          <span>{fi.archive.unreviewed(unreviewed)}</span>
        ) : isAsking ? (
          confirmation("archive", year, fi.archive.confirmArchive(year, receipts, lines, images))
        ) : (
          <button
            type="button"
            disabled={isBusy}
            onClick={() => setAsking({ kind: "archive", year })}
          >
            {fi.archive.archive}
          </button>
        )}
      </li>
    );
  }

  function archivedItem(archived: ArchivedYear) {
    const { year, receipts, lines } = archived;
    const isAsking = asking?.kind === "delete" && asking.year === year;
    return (
      <li key={year}>
        {year}: {fi.archive.archivedCounts(receipts, lines)}{" "}
        <a href={`${PAGE_PATHS.archive}/${year}`} onClick={(event) => open(event, year)}>
          {fi.archive.show}
        </a>{" "}
        {isAsking ? (
          confirmation("delete", year, fi.archive.confirmDelete(year, receipts, lines))
        ) : (
          <button
            type="button"
            disabled={isBusy}
            onClick={() => setAsking({ kind: "delete", year })}
          >
            {fi.archive.delete}
          </button>
        )}
      </li>
    );
  }

  return (
    <section aria-labelledby="archive-heading">
      <h2 id="archive-heading">{fi.archive.heading}</h2>
      {error && <p role="alert">{error}</p>}
      {report && (
        <div role="status">
          <p>{report.text}</p>
          {report.notMoved.map((name) => (
            <p key={name}>{fi.archive.notMoved(name)}</p>
          ))}
        </div>
      )}
      {overview && (
        <>
          <h3 id="archive-candidates">{fi.archive.candidatesHeading}</h3>
          {overview.candidates.length === 0 ? (
            <p>{fi.archive.noCandidates}</p>
          ) : (
            <ul aria-labelledby="archive-candidates">{overview.candidates.map(candidateItem)}</ul>
          )}
          <h3 id="archive-archived">{fi.archive.archivedHeading}</h3>
          {overview.archived.length === 0 ? (
            <p>{fi.archive.noArchived}</p>
          ) : (
            <ul aria-labelledby="archive-archived">{overview.archived.map(archivedItem)}</ul>
          )}
        </>
      )}
    </section>
  );
}
