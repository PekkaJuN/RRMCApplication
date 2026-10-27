# Glossary

## Overview

Domain terms used across the docs, specs and code. The UI is in Finnish, so each term also
gives the Finnish word the user sees.

## Terms

| Term | Finnish | Meaning |
|---|---|---|
| Catalog | — | The groups, categories and products together; owned by [categorization](subsystems/categorization/README.md) |
| Category | kategoria | Holds products. Belongs to one group or to none. Every product has exactly one category |
| Group | ryhmä, yläryhmä | Holds categories, never products. Cannot be nested, so the hierarchy has at most two levels |
| Product | tuote | A named item with one category; the app's memory of where a purchase belongs |
| Default list | oletuskategoriat | The groups and categories created once on the first start ([PRD 6.9](../specs/PRD.md#69-default-categories)) |
| Display name | — | A name as shown: Unicode NFC, trimmed, inner whitespace collapsed to one space |
| Normalized name | — | The display name, case-folded; stored as `name_key` and used for every comparison ([names](subsystems/categorization/README.md#names)) |

## Subsystems

- [categorization](subsystems/categorization/README.md) — catalog terms

## Related Documents

- [projectdescription.md](projectdescription.md)
- [datamodel.md](datamodel.md)
