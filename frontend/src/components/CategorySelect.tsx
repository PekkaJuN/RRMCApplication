import type { CatalogItem } from "../api/catalog";
import { fi } from "../i18n/fi";

interface Props {
  label: string;
  items: CatalogItem[];
  value: number | null;
  onChange: (id: number | null) => void;
  /** The filter variant also offers "Kaikki" and whole groups. */
  isFilter?: boolean;
  disabled?: boolean;
}

/**
 * A category dropdown. Groups are `optgroup` headings, which cannot be chosen (FR-17);
 * categories without a group follow the groups. Items are shown in the backend's order.
 */
export function CategorySelect({ label, items, value, onChange, isFilter, disabled }: Props) {
  const groups = items.filter((item) => item.kind === "group");
  const ungrouped = items.filter((item) => item.kind === "category" && item.parent_id === null);
  const option = (item: CatalogItem) => (
    <option key={item.id} value={item.id}>
      {item.name}
    </option>
  );

  return (
    <select
      aria-label={label}
      value={value ?? ""}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
    >
      {isFilter ? (
        <option value="">{fi.products.all}</option>
      ) : (
        <option value="" disabled>
          {fi.products.chooseCategory}
        </option>
      )}
      {groups.map((group) => (
        <optgroup key={group.id} label={group.name}>
          {isFilter && <option value={group.id}>{fi.products.wholeGroup(group.name)}</option>}
          {items.filter((item) => item.parent_id === group.id).map(option)}
        </optgroup>
      ))}
      {ungrouped.map(option)}
    </select>
  );
}
