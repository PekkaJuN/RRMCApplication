import type { Comparison, ComparisonRow, ComparisonTotal, WeekFigures } from "../api/budget";
import { formatCents } from "../format";
import { fi } from "../i18n/fi";
import { columnHeading } from "../period";

interface Props {
  comparison: Comparison;
}

/** An amount cell; `isOver` adds the text, so the meaning does not depend on color (PC6). */
function AmountCell({ cents, isOver = false }: { cents: number; isOver?: boolean }) {
  return (
    <td className="amount">
      {formatCents(cents)}
      {isOver && ` ${fi.comparison.over}`}
    </td>
  );
}

function rowName(row: ComparisonRow): string {
  return row.name ?? fi.totals.noCategory;
}

function rowKey(row: ComparisonRow): string {
  return `${row.kind}-${row.id ?? "none"}`;
}

function MonthCells({ figures }: { figures: ComparisonTotal }) {
  return (
    <>
      <AmountCell cents={figures.budget_cents} />
      <AmountCell cents={figures.actual_cents} />
      <AmountCell cents={figures.remaining_cents} isOver={figures.remaining_cents < 0} />
    </>
  );
}

/** The month table: budget, actual spending and remaining per row. */
export function ComparisonMonthTable({ comparison }: Props) {
  return (
    <div className="table-box">
      <table aria-label={fi.comparison.month}>
        <caption>{fi.comparison.month}</caption>
        <thead>
          <tr>
            <th scope="col">{fi.totals.category}</th>
            <th scope="col" className="amount">
              {fi.comparison.budget}
            </th>
            <th scope="col" className="amount">
              {fi.comparison.actual}
            </th>
            <th scope="col" className="amount">
              {fi.comparison.remaining}
            </th>
          </tr>
        </thead>
        <tbody>
          {comparison.rows.map((row) => (
            <tr key={rowKey(row)}>
              <th scope="row">{rowName(row)}</th>
              <MonthCells figures={row} />
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="row-total">
            <th scope="row">{fi.totals.total}</th>
            <MonthCells figures={comparison.total} />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/** The week table: a heading per ISO week over its budget and actual spending. */
export function ComparisonWeekTable({ comparison }: Props) {
  function weekCells(weeks: WeekFigures[]) {
    return weeks.flatMap((week, index) => {
      const key = comparison.weeks[index]?.key;
      return [
        <AmountCell key={`${key}-budget`} cents={week.budget_cents} />,
        <AmountCell
          key={`${key}-actual`}
          cents={week.actual_cents}
          isOver={week.actual_cents > week.budget_cents}
        />,
      ];
    });
  }

  return (
    <div className="table-box">
      <table aria-label={fi.comparison.weeks}>
        <caption>{fi.comparison.weeks}</caption>
        <thead>
          <tr>
            <th scope="col" rowSpan={2}>
              {fi.totals.category}
            </th>
            {comparison.weeks.map((week) => (
              <th key={week.key} scope="colgroup" colSpan={2} className="amount">
                {columnHeading(week, "week")}
              </th>
            ))}
          </tr>
          <tr>
            {comparison.weeks.flatMap((week) => [
              <th key={`${week.key}-budget`} scope="col" className="amount">
                {fi.comparison.budget}
              </th>,
              <th key={`${week.key}-actual`} scope="col" className="amount">
                {fi.comparison.actual}
              </th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {comparison.rows.map((row) => (
            <tr key={rowKey(row)}>
              <th scope="row">{rowName(row)}</th>
              {weekCells(row.weeks)}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="row-total">
            <th scope="row">{fi.totals.total}</th>
            {weekCells(comparison.total.weeks)}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
