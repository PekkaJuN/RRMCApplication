import { useState, type ReactElement } from "react";
import type { ArchiveRow, ArchiveTotals } from "../api/archive";
import { formatCents } from "../format";
import { fi } from "../i18n/fi";

interface Props {
  totals: ArchiveTotals;
}

const DEPTH_CLASS = ["row-group", "row-category", "row-product"] as const;

function rowName(row: ArchiveRow): string {
  return row.name ?? fi.totals.noCategory;
}

/** A key per row that stays the same while the page is open: the names on the way down. */
function rowKey(parent: string, row: ArchiveRow): string {
  return `${parent}/${row.kind}:${row.name ?? ""}`;
}

/** The keys open on opening: the groups, so their categories show (archiving PC15). */
function openGroups(rows: ArchiveRow[]): Set<string> {
  return new Set(rows.filter((row) => row.kind === "group").map((row) => rowKey("", row)));
}

/** The totals of an archived year: groups, categories and products by month (PC11, PC15). */
export function ArchiveTotalsTable({ totals }: Props) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => openGroups(totals.rows));
  const label = fi.archive.yearHeading(totals.year);

  function toggle(key: string) {
    const next = new Set(expanded);
    if (!next.delete(key)) {
      next.add(key);
    }
    setExpanded(next);
  }

  function amountCells(row: { months: number[]; total: number }) {
    return [
      ...row.months.map((amount, index) => (
        <td key={totals.months[index]} className="amount">
          {formatCents(amount)}
        </td>
      )),
      <td key="year" className="amount">
        {formatCents(row.total)}
      </td>,
    ];
  }

  function rowsOf(row: ArchiveRow, depth: number, parent: string): ReactElement[] {
    const key = rowKey(parent, row);
    const name = rowName(row);
    const hasChildren = row.children.length > 0;
    const open = expanded.has(key);
    const toggleLabel =
      row.kind === "group"
        ? open
          ? fi.archive.hideCategories(name)
          : fi.archive.showCategories(name)
        : open
          ? fi.archive.hideProducts(name)
          : fi.archive.showProducts(name);
    return [
      <tr key={key} className={DEPTH_CLASS[depth]}>
        <th scope="row" className="archive-name">
          {hasChildren && (
            <>
              <button
                type="button"
                aria-expanded={open}
                aria-label={toggleLabel}
                onClick={() => toggle(key)}
              >
                {open ? "−" : "+"}
              </button>{" "}
            </>
          )}
          <span>{name}</span>
        </th>
        {amountCells(row)}
      </tr>,
      ...(hasChildren && open
        ? row.children.flatMap((child) => rowsOf(child, depth + 1, key))
        : []),
    ];
  }

  return (
    <div className="table-box table-box-wide">
      <table aria-label={label} className="archive-table">
        <caption>{label}</caption>
        <thead>
          <tr>
            <th scope="col" className="archive-name">
              {fi.archive.name}
            </th>
            {totals.months.map((month) => (
              <th key={month} scope="col" className="amount">
                {month}
              </th>
            ))}
            <th scope="col" className="amount">
              {fi.archive.year}
            </th>
          </tr>
        </thead>
        <tbody>{totals.rows.flatMap((row) => rowsOf(row, 0, ""))}</tbody>
        <tfoot>
          <tr className="row-total">
            <th scope="row" className="archive-name">
              {fi.totals.total}
            </th>
            {amountCells({ months: totals.month_totals, total: totals.total })}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
