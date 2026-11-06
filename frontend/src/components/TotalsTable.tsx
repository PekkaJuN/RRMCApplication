import type { TotalsColumn, TotalsRow } from "../api/totals";
import { formatCents } from "../format";
import { fi } from "../i18n/fi";
import { columnHeading, type PeriodUnit } from "../period";

interface Props {
  label: string;
  /** Which columns these are: weeks or months. */
  unit: PeriodUnit;
  columns: TotalsColumn[];
  rows: TotalsRow[];
  totals: number[];
  /** The ids of the expanded groups; shared by both tables of the page. */
  expanded: ReadonlySet<number>;
  onToggle: (groupId: number) => void;
}

/** One totals table: a row per group, category without a group and no category, then the
 * total; a group's categories show when it is expanded (totals spec PC4). */
export function TotalsTable({ label, unit, columns, rows, totals, expanded, onToggle }: Props) {
  const amountsOf = (row: TotalsRow) => (unit === "week" ? row.weeks : row.months);

  function amountCells(amounts: number[]) {
    return amounts.map((amount, index) => (
      <td key={columns[index]?.key} className="amount">
        {formatCents(amount)}
      </td>
    ));
  }

  function rowsOf(row: TotalsRow) {
    if (row.kind !== "group" || row.id === null) {
      return [
        <tr key={`${row.kind}-${row.id ?? "none"}`}>
          <th scope="row">{row.name ?? fi.totals.noCategory}</th>
          {amountCells(amountsOf(row))}
        </tr>,
      ];
    }
    const groupId = row.id;
    const name = row.name ?? "";
    const open = expanded.has(groupId);
    return [
      <tr key={`group-${groupId}`} className="row-group">
        <th scope="row">
          <button
            type="button"
            aria-expanded={open}
            aria-label={open ? fi.totals.collapse(name) : fi.totals.expand(name)}
            onClick={() => onToggle(groupId)}
          >
            {open ? "−" : "+"}
          </button>{" "}
          {name}
        </th>
        {amountCells(amountsOf(row))}
      </tr>,
      ...(open
        ? row.categories.map((category) => (
            <tr key={`category-${category.id ?? "none"}`} className="row-category">
              <th scope="row">{category.name}</th>
              {amountCells(amountsOf(category))}
            </tr>
          ))
        : []),
    ];
  }

  return (
    <div className="table-box">
      <table aria-label={label}>
        <caption>{label}</caption>
        <thead>
          <tr>
            <th scope="col">{fi.totals.category}</th>
            {columns.map((column) => (
              <th key={column.key} scope="col" className="amount">
                {columnHeading(column, unit)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{rows.flatMap(rowsOf)}</tbody>
        <tfoot>
          <tr className="row-total">
            <th scope="row">{fi.totals.total}</th>
            {amountCells(totals)}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
