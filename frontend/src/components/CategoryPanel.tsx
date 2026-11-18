import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { createCategory, type CatalogItem } from "../api/catalog";
import type { ApiResult } from "../api/client";
import { fi } from "../i18n/fi";

interface Props {
  items: CatalogItem[];
  /** The selected group or category; null is "Kaikki tuotteet". */
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  /** Called after a successful change, so the page reloads the lists and counts. */
  onChanged: () => void;
}

type FormKind = "group" | "category";

/**
 * The category column (products two columns PC2, PC3, PC7): the buttons that open the new
 * group and new category forms, kept above the tree so a long tree does not hide them; then
 * a tree of "Kaikki tuotteet", the groups with their categories and the categories without
 * a group.
 */
export function CategoryPanel({ items, selectedId, onSelect, onChanged }: Props) {
  // Closed groups are stored, not open ones, so every group starts open, also a new one.
  const [closedGroups, setClosedGroups] = useState<ReadonlySet<number>>(new Set());
  const [openForm, setOpenForm] = useState<FormKind | null>(null);
  const baseId = useId();
  const groups = items.filter((item) => item.kind === "group");
  const ungrouped = items.filter((item) => item.kind === "category" && item.parent_id === null);
  const selected = items.find((item) => item.id === selectedId);
  const suggestedGroupId = selected?.kind === "group" ? selected.id : (selected?.parent_id ?? null);
  const formId = (kind: FormKind) => `${baseId}-${kind}-form`;

  const toggleGroup = (id: number) =>
    setClosedGroups((current) => {
      const next = new Set(current);
      if (!next.delete(id)) {
        next.add(id);
      }
      return next;
    });

  const selectButton = (id: number | null, name: string) => (
    <button
      type="button"
      className="tree-item"
      aria-pressed={id === selectedId}
      onClick={() => onSelect(id)}
    >
      {name}
    </button>
  );

  const category = (item: CatalogItem) => (
    <li key={item.id}>
      {selectButton(item.id, item.name)}{" "}
      <span data-count>{fi.categories.productCount(item.product_count ?? 0)}</span>
    </li>
  );

  const group = (item: CatalogItem) => {
    const children = items.filter((child) => child.parent_id === item.id);
    const isOpen = !closedGroups.has(item.id);
    const listId = `${baseId}-group-${item.id}`;
    return (
      <li key={item.id}>
        {children.length > 0 ? (
          <button
            type="button"
            className="tree-toggle"
            aria-expanded={isOpen}
            aria-controls={listId}
            aria-label={
              isOpen
                ? fi.categories.hideCategories(item.name)
                : fi.categories.showCategories(item.name)
            }
            onClick={() => toggleGroup(item.id)}
          >
            {isOpen ? "−" : "+"}
          </button>
        ) : (
          <span className="tree-toggle-space" />
        )}
        {selectButton(item.id, item.name)}{" "}
        <span data-count>{fi.categories.categoryCount(item.category_count ?? 0)}</span>
        {children.length > 0 && isOpen && <ul id={listId}>{children.map(category)}</ul>}
      </li>
    );
  };

  const formButton = (kind: FormKind, label: string) => (
    <button
      type="button"
      className="button"
      aria-expanded={openForm === kind}
      aria-controls={formId(kind)}
      onClick={() => setOpenForm((current) => (current === kind ? null : kind))}
    >
      {label}
    </button>
  );

  return (
    <section className="category-column" aria-labelledby="categories-heading">
      <h3 id="categories-heading">{fi.categories.heading}</h3>
      <p>
        {formButton("group", fi.categories.newGroup)}
        {formButton("category", fi.categories.newCategory)}
      </p>
      {openForm === "group" && (
        <AddForm
          id={formId("group")}
          label={fi.categories.newGroup}
          nameLabel={fi.categories.groupName}
          onCancel={() => setOpenForm(null)}
          onAdd={(name) => createCategory({ name, kind: "group" })}
          onAdded={onChanged}
        />
      )}
      {openForm === "category" && (
        <AddForm
          id={formId("category")}
          label={fi.categories.newCategory}
          nameLabel={fi.categories.categoryName}
          groups={groups}
          initialParentId={suggestedGroupId}
          onCancel={() => setOpenForm(null)}
          onAdd={(name, parentId) =>
            createCategory({ name, kind: "category", parent_id: parentId ?? null })
          }
          onAdded={onChanged}
        />
      )}
      <ul className="category-tree">
        <li>{selectButton(null, fi.products.allProducts)}</li>
        {groups.map(group)}
        {ungrouped.map(category)}
      </ul>
    </section>
  );
}

interface AddFormProps {
  id: string;
  label: string;
  nameLabel: string;
  /** When given, the form also asks for the group of the new category. */
  groups?: CatalogItem[];
  /** The group the dropdown starts at; read once, when the form opens. */
  initialParentId?: number | null;
  onCancel: () => void;
  onAdd: (name: string, parentId: number | null) => Promise<ApiResult<unknown>>;
  onAdded: () => void;
}

function AddForm({
  id,
  label,
  nameLabel,
  groups,
  initialParentId = null,
  onCancel,
  onAdd,
  onAdded,
}: AddFormProps) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<number | null>(initialParentId);
  // Errors are shown next to the form whose action caused them (product management AC27).
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  // The form opens from a button, so the focus moves to its first field (AC15).
  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = await onAdd(name, parentId);
    if (result.ok) {
      setError(null);
      setName("");
      onAdded();
    } else {
      setError(result.error.message);
    }
  };

  return (
    <form id={id} aria-label={label} onSubmit={(event) => void submit(event)}>
      <input
        ref={nameRef}
        aria-label={nameLabel}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />{" "}
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
      )}{" "}
      <button type="submit">{fi.actions.add}</button>{" "}
      <button type="button" onClick={onCancel}>
        {fi.actions.cancel}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
