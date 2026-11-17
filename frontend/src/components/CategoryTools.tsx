import { useState, type FormEvent } from "react";
import { deleteCategory, updateCategory, type CatalogItem, type Kind } from "../api/catalog";
import type { ApiResult } from "../api/client";
import { fi } from "../i18n/fi";
import { ConfirmDelete } from "./ConfirmDelete";

interface Props {
  item: CatalogItem;
  groups: CatalogItem[];
  /** Called after a successful change, so the page reloads the lists and counts. */
  onChanged: () => void;
}

/** The tools of the selected group or category: rename, move, convert, delete (PC6). */
export function CategoryTools({ item, groups, onChanged }: Props) {
  const [draft, setDraft] = useState<string | null>(null);
  // The error stays beside the tools whose action caused it (product management AC27).
  const [error, setError] = useState<string | null>(null);
  const isGroup = item.kind === "group";
  const nameLabel = isGroup ? fi.categories.groupName : fi.categories.categoryName;
  const convertTo: Kind = isGroup ? "category" : "group";

  const run = async (action: () => Promise<ApiResult<unknown>>) => {
    const result = await action();
    setError(result.ok ? null : result.error.message);
    if (result.ok) {
      onChanged();
    }
    return result.ok;
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (draft !== null && (await run(() => updateCategory(item.id, { name: draft })))) {
      setDraft(null);
    }
  };

  return (
    <div className="category-tools">
      {draft === null ? (
        <button type="button" onClick={() => setDraft(item.name)}>
          {fi.actions.rename}
        </button>
      ) : (
        <form onSubmit={(event) => void save(event)}>
          <input
            aria-label={nameLabel}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit">{fi.actions.save}</button>
          <button type="button" onClick={() => setDraft(null)}>
            {fi.actions.cancel}
          </button>
        </form>
      )}{" "}
      {!isGroup && (
        <select
          aria-label={fi.categories.move(item.name)}
          value={item.parent_id ?? ""}
          onChange={(event) => {
            const parentId = event.target.value === "" ? null : Number(event.target.value);
            void run(() => updateCategory(item.id, { parent_id: parentId }));
          }}
        >
          <option value="">{fi.categories.noGroup}</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      )}{" "}
      <button
        type="button"
        onClick={() => void run(() => updateCategory(item.id, { kind: convertTo }))}
      >
        {isGroup ? fi.categories.toCategory : fi.categories.toGroup}
      </button>{" "}
      <ConfirmDelete onConfirm={() => void run(() => deleteCategory(item.id))} />
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
