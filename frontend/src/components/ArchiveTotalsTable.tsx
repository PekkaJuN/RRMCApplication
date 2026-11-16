import { useId, useState, type ReactElement } from "react";
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

/** The keys of the rows that open a level: the groups, and the categories at the top or in
 * a group (table-expand-all P1). Every category has products, because rows without lines
 * are left out of the totals (archiving PC11). */
function levelKeys(rows: ArchiveRow[]): { groups: string[]; categories: string[] } {
  const groups: string[] = [];
  const categories: string[] = [];
  for (const row of rows) {
    const key = rowKey("", row);
    if (row.kind === "group") {
      groups.push(key);
      categories.push(...row.children.map((category) => rowKey(key, category)));
    } else {
      categories.push(key);
    }
  }
  return { groups, categories };
}

/** The totals of an archived year: groups, categories and products by month (PC11, PC15). */
export function ArchiveTotalsTable({ totals }: Props) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => openGroups(totals.rows));
  const label = fi.archive.yearHeading(totals.year);
  const tableId = useId();
  const levels = levelKeys(totals.rows);
  const allOpen = (keys: string[]) => keys.every((key) => expanded.has(key));
  // A level shows when its rows and the rows above it are open (PC2, PC3).
  const categoriesOpen = allOpen(levels.groups);
  const productsOpen = categoriesOpen && allOpen(levels.categories);

  function toggleCategories() {
    setExpanded(categoriesOpen ? new Set() : new Set([...expanded, ...levels.groups]));
  }

  function toggleProducts() {
    if (productsOpen) {
      const next = new Set(expanded);
      levels.categories.forEach((key) => next.delete(key));
      setExpanded(next);
    } else {
      setExpanded(new Set([...expanded, ...levels.groups, ...levels.categories]));
    }
  }

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
    <>
      <p>
        {levels.groups.length > 0 && (
          <button
            type="button"
            className="button"
            aria-expanded={categoriesOpen}
            aria-controls={tableId}
            onClick={toggleCategories}
          >
            {categoriesOpen ? fi.archive.hideAllCategories : fi.archive.showAllCategories}
          </button>
        )}
        {levels.categories.length > 0 && (
          <button
            type="button"
            className="button"
            aria-expanded={productsOpen}
            aria-controls={tableId}
            onClick={toggleProducts}
          >
            {productsOpen ? fi.archive.hideAllProducts : fi.archive.showAllProducts}
          </button>
        )}
      </p>
      <div className="table-box table-box-wide">
        <table id={tableId} aria-label={label} className="archive-table">
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
    </>
  );
}
