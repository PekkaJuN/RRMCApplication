# Project Description

- **Status:** In Progress (no source code yet)
- **Updated:** 2026-10-22

## Overview

RRMCApplication (Receipt Reader Mapper Calculator) is a local app that turns photos of
shopping receipts into categorized spending. It reads each receipt, splits it into line
items, puts every line into a category, and shows how much was spent per category each week
and each month. The user checks and corrects the result in a Finnish-language UI, and the app
remembers each correction.

This document explains what the product is and for whom. The detailed requirements are in
[the PRD](../specs/PRD.md); how the system is built is in [architecture.md](architecture.md).

## Why it exists

Knowing where grocery and household money goes needs line-level data, but that data is only
on paper receipts. Typing receipts in by hand takes too long, and cloud receipt services send
personal purchase data to third parties. RRMCApplication does the reading and categorizing on
the user's own computer, so the data never leaves it
([PRD goals](../specs/PRD.md#2-goals)).

## Users

One person (one household), on one Windows computer. They photograph their own receipts,
copy the images into a folder, and review the results in the browser. They are comfortable
starting a local app. There are no accounts, no login and no per-person buyer information
([PRD section 4](../specs/PRD.md#4-user)).

## Key features

| Feature | What the user gets | PRD |
|---|---|---|
| Folder import | Copy images into the import folder and press a button. Each image is read once; duplicates are skipped, imported images move to a done folder and failed ones to a failed folder. | FR-1–FR-5, FR-45 |
| Receipt reading | Store, date, lines and total read from the image with local OCR and a local language model, following Finnish receipt conventions. | FR-6–FR-10 |
| Categorization that learns | Each line gets a category: a product corrected before keeps its category, other lines get a suggestion from the model. | FR-11–FR-15 |
| Review | The receipt image beside an editable table of its lines, with a warning when the lines do not add up to the receipt total. | FR-16–FR-21, FR-43 |
| Products and categories | Manage the product list and the categories, which can be grouped (e.g. Ruoka, Auto). | FR-33–FR-39 |
| Totals | Spending per category and group, per ISO week and per month, by purchase date. | FR-22–FR-25, FR-44 |
| Export | CSV export of lines and totals; Google Sheets in a later release. | FR-26–FR-28 |

Releases and the order of work are in [PRD section 9](../specs/PRD.md#9-releases).

## Business domain

The app works with Finnish grocery and household receipts. The rules that shape it:

- **Lines and amounts.** A line is one item with its amount. A discount printed under an
  item is merged into that item, and so is a bottle or can deposit (pantti), because the
  deposit is part of the item's price.
- **Deposit refunds.** A deposit refund (panttipalautus) is a negative line of its own. It is
  not a cost or a saving, so it has no category and is left out of all spending totals. It
  only takes part in checking the lines against the printed receipt total.
- **Categories and groups.** Spending is counted per category, such as Maitotuotteet or
  Polttoaineet. Categories can sit in a group, such as Ruoka or Auto, whose total is the sum
  of its categories. A product is categorized by what it is, not by how it is stored: frozen
  fish is Kala, not Pakasteet. The default list is in
  [PRD section 6.9](../specs/PRD.md#69-default-categories).
- **Time.** Totals use the purchase date, not the import date. Weeks are ISO 8601 weeks
  (Monday to Sunday).
- **Money** is euros, handled as whole cents.

Domain terms are defined in the [PRD glossary](../specs/PRD.md#13-glossary).

## Principles

- **Local and private.** Images, OCR text, model calls and the database stay on the user's
  computer. The app listens only on `127.0.0.1`.
- **Correct over automatic.** The app suggests; the user decides. Every value can be edited,
  and corrections are reused.
- **Nothing is lost.** An image moves out of the import folder only after its data is saved,
  or into the failed folder with the reason.

## Out of scope

Multiple users, hosting on a server, a mobile app, budgeting or forecasting, bank
integration, and cloud OCR or cloud models. See [PRD non-goals](../specs/PRD.md#3-non-goals).

## Subsystems

See the [component map in architecture.md](architecture.md#component-map). Subsystem docs are
not written yet.

## Related Documents

- [PRD](../specs/PRD.md): goals, requirements and open questions
- [Architecture](architecture.md): components, data flow and stack
- [ADR 0001: Technology stack](adr/0001-tech-stack.md)
- [Content plan](content-plan.md): documentation index
