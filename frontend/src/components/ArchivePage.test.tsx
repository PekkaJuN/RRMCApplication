import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { answerArchive, OVERVIEW } from "../test/archive";
import { ArchivePage } from "./ArchivePage";

// Archiving spec PC14.

const AFTER_ARCHIVING = {
  archived: [
    { year: 2025, receipts: 12, lines: 140, images: 11 },
    { year: 2023, receipts: 12, lines: 140, images: 11 },
  ],
  candidates: [{ year: 2024, receipts: 3, lines: 20, images: 3, unreviewed: 1 }],
};

const candidates = () => screen.getByRole("list", { name: "Arkistoitavat vuodet" });
const archived = () => screen.getByRole("list", { name: "Arkistoidut vuodet" });

/** Waits until the list holds the year's item; the lists reload after every request. */
function item(list: () => HTMLElement, year: number) {
  return waitFor(() => {
    const found = within(list())
      .getAllByRole("listitem")
      .find((element) => element.textContent?.startsWith(String(year)));
    if (!found) {
      throw new Error(`no item ${year}`);
    }
    return found;
  });
}

const candidate = (year: number) => item(candidates, year);
const archivedYear = (year: number) => item(archived, year);

it("archiving AC33: archiving a year asks first, then moves it to the archived list", async () => {
  const requests = answerArchive({ after: AFTER_ARCHIVING });
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={vi.fn()} />);

  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));

  const item = await candidate(2023);
  expect(item).toHaveTextContent(
    "Arkistoidaan vuosi 2023: 12 kuittia, 140 riviä ja 11 kuvaa. Arkistointia ei voi perua. " +
      "Ota varmuuskopio ennen arkistointia.",
  );
  expect(requests.archived).toEqual([]);

  await user.click(within(item).getByRole("button", { name: "Arkistoi" }));

  expect(await archivedYear(2023)).toBeInTheDocument();
  expect(requests.archived).toEqual([2023]);
  expect(within(candidates()).queryByText(/^2023/)).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Vuosi 2023 arkistoitu: 12 kuittia ja 140 riviä.",
  );
});

it("archiving AC34: a year with unreviewed receipts has no archive button", async () => {
  answerArchive();
  render(<ArchivePage onOpenYear={vi.fn()} />);

  const item = await candidate(2024);

  expect(item).toHaveTextContent("Tarkistamattomia kuitteja: 1");
  expect(within(item).queryByRole("button", { name: "Arkistoi" })).not.toBeInTheDocument();
});

it("archiving AC35: an image that was not moved is named", async () => {
  answerArchive({
    result: { year: 2023, receipts: 12, lines: 140, images_moved: 10, images_not_moved: ["a.jpg"] },
  });
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={vi.fn()} />);

  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));
  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));

  expect(
    await screen.findByText("Kuvaa ei voitu siirtää arkistokansioon: a.jpg"),
  ).toBeInTheDocument();
});

it("archiving AC36: Peruuta sends nothing", async () => {
  const requests = answerArchive();
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={vi.fn()} />);

  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));
  await user.click(within(await candidate(2023)).getByRole("button", { name: "Peruuta" }));

  expect(requests.archived).toEqual([]);
  expect(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" })).toBeEnabled();
});

it("archiving AC36: a second click while archiving sends nothing", async () => {
  let release = () => {};
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requests = answerArchive({ hold });
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={vi.fn()} />);
  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));

  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));
  const again = within(await candidate(2023)).getByRole("button", { name: "Arkistoi" });
  expect(again).toBeDisabled();
  await user.click(again);
  release();

  await waitFor(() => expect(requests.overviews).toBe(2));
  expect(requests.archived).toEqual([2023]);
});

it("archiving AC37: a refusal shows the backend's message and reloads the lists", async () => {
  const requests = answerArchive({
    archiveError: {
      status: 409,
      body: {
        error: "unreviewed_receipts",
        message: "Vuotta ei voi arkistoida: vuodella on 1 tarkistamaton kuitti.",
        count: 1,
      },
    },
  });
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={vi.fn()} />);

  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));
  await user.click(within(await candidate(2023)).getByRole("button", { name: "Arkistoi" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Vuotta ei voi arkistoida: vuodella on 1 tarkistamaton kuitti.",
  );
  await waitFor(() => expect(requests.overviews).toBe(2));
});

it("archiving AC38: deleting an archived year asks first", async () => {
  const requests = answerArchive({ after: { ...OVERVIEW, archived: [] } });
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={vi.fn()} />);

  await user.click(
    within(await archivedYear(2025)).getByRole("button", { name: "Poista pysyvästi" }),
  );

  const item = await archivedYear(2025);
  expect(item).toHaveTextContent(
    "Poistetaan vuoden 2025 arkisto pysyvästi: 12 kuittia ja 140 riviä. Kuvat jäävät " +
      "arkistokansioon. Poistoa ei voi perua. Ota varmuuskopio ennen poistoa.",
  );
  await user.click(within(item).getByRole("button", { name: "Poista pysyvästi" }));

  expect(await screen.findByText("Ei arkistoituja vuosia.")).toBeInTheDocument();
  expect(requests.deleted).toEqual([2025]);
});

it("archiving AC39: Näytä opens the year", async () => {
  answerArchive();
  const onOpenYear = vi.fn();
  const user = userEvent.setup();
  render(<ArchivePage onOpenYear={onOpenYear} />);

  const link = within(await archivedYear(2025)).getByRole("link", { name: "Näytä" });
  expect(link).toHaveAttribute("href", "/arkisto/2025");
  await user.click(link);

  expect(onOpenYear).toHaveBeenCalledWith(2025);
});

it("archiving PC14: empty lists say so", async () => {
  answerArchive({ overview: { archived: [], candidates: [] } });
  render(<ArchivePage onOpenYear={vi.fn()} />);

  expect(await screen.findByText("Ei arkistoitavia vuosia.")).toBeInTheDocument();
  expect(screen.getByText("Ei arkistoituja vuosia.")).toBeInTheDocument();
});
