import { useState, type FormEvent, type ReactNode } from "react";
import {
  createCategory,
  deleteCategory,
  updateCategory,
  type CatalogItem,
  type Kind,
} from "../api/catalog";
import type { ApiResult } from "../api/client";
import { fi } from "../i18n/fi";
import { ConfirmDelete } from "./ConfirmDelete";

interface Props {
  items: CatalogItem[];
  /** Called after a successful change, so the page reloads the lists and counts. */
  onChanged: () => void;
}

type Run = (key: string, action: () => Promise<ApiResult<unknown>>) => Promise<boolean>;

/** Groups with their categories, then the categories without a group (PC9). */
export function CategoryPanel({ items, onChanged }: Props) {
  // Errors are shown next to the item or form whose action caused them (AC27).
  const [errors, setErrors] = useState<Record<string, string>>({});
  const groups = items.filter((item) => item.kind === "group");
  const ungrouped = items.filter((item) => item.kind === "category" && item.parent_id === null);

  const run: Run = async (key, action) => {
    const result = await action();
    setErrors((current) => {
      const next = { ...current };
      if (result.ok) {
        delete next[key];
      } else {
        next[key] = result.error.message;
      }
      return next;
    });
    if (result.ok) {
      onChanged();
    }
    return result.ok;
  };

  const entry = (item: CatalogItem) => (
    <Entry key={item.id} item={item} groups={groups} error={errors[`item-${item.id}`]} run={run}>
      {item.kind === "group" && (
        <ul>{items.filter((child) => child.parent_id === item.id).map((child) => entry(child))}</ul>
      )}
    </Entry>
  );

  return (
    <section aria-labelledby="categories-heading">
      <h2 id="categories-heading">{fi.categories.heading}</h2>
      <ul>
        {groups.map(entry)}
        {ungrouped.map(entry)}
      </ul>
      <AddForm
        label={fi.categories.newGroup}
        nameLabel={fi.categories.groupName}
        error={errors.newGroup}
        onAdd={(name) => run("newGroup", () => createCategory({ name, kind: "group" }))}
      />
      <AddForm
        label={fi.categories.newCategory}
        nameLabel={fi.categories.categoryName}
        groups={groups}
        error={errors.newCategory}
        onAdd={(name, parentId) =>
          run("newCategory", () =>
            createCategory({ name, kind: "category", parent_id: parentId ?? null }),
          )
        }
      />
    </section>
  );
}

interface EntryProps {
  item: CatalogItem;
  groups: CatalogItem[];
  error: string | undefined;
  run: Run;
  children: ReactNode;
}

function Entry({ item, groups, error, run, children }: EntryProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const key = `item-${item.id}`;
  const isGroup = item.kind === "group";
  const nameLabel = isGroup ? fi.categories.groupName : fi.categories.categoryName;
  const convertTo: Kind = isGroup ? "category" : "group";

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (draft !== null && (await run(key, () => updateCategory(item.id, { name: draft })))) {
      setDraft(null);
    }
  };

  return (
    <li>
      {draft === null ? (
        <>
          <span data-name>{item.name}</span>{" "}
          <span>
            {isGroup
              ? fi.categories.categoryCount(item.category_count ?? 0)
              : fi.categories.productCount(item.product_count ?? 0)}
          </span>{" "}
          <button type="button" onClick={() => setDraft(item.name)}>
            {fi.actions.rename}
          </button>
        </>
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
            void run(key, () => updateCategory(item.id, { parent_id: parentId }));
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
        onClick={() => void run(key, () => updateCategory(item.id, { kind: convertTo }))}
      >
        {isGroup ? fi.categories.toCategory : fi.categories.toGroup}
      </button>{" "}
      <ConfirmDelete onConfirm={() => void run(key, () => deleteCategory(item.id))} />
      {error && <p role="alert">{error}</p>}
      {children}
    </li>
  );
}

interface AddFormProps {
  label: string;
  nameLabel: string;
  /** When given, the form also asks for the group of the new category. */
  groups?: CatalogItem[];
  error: string | undefined;
  onAdd: (name: string, parentId: number | null) => Promise<boolean>;
}

function AddForm({ label, nameLabel, groups, error, onAdd }: AddFormProps) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<number | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (await onAdd(name, parentId)) {
      setName("");
    }
  };

  return (
    <form aria-label={label} onSubmit={(event) => void submit(event)}>
      <h3>{label}</h3>
      <input
        aria-label={nameLabel}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      {groups && (
        <select
          aria-label={fi.categories.group}
          value={parentId ?? ""}
          onChange={(event) =>
            setParentId(event.target.value === "" ? null : Number(event.target.value))
          }
        >
          <option value="">{fi.categories.noGroup}</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      )}
      <button type="submit">{fi.actions.add}</button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
