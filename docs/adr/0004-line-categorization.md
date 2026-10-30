# 0004. Line categorization: remembered products first, then one separate model call

- Status: accepted
- Date: 2026-10-30

## Context

Every receipt line needs a category (PRD FR-12). The catalog already remembers the
category of each product the user has named or corrected. Lines the catalog does not know
need a suggestion from the local model, which runs on the CPU. There, the slow part is
writing the answer: about 10 output tokens per second against about 60 prompt tokens per
second (PRD open question 1).

There were two ways to ask the model:

1. Add a category field to every line of the reading answer
   ([ADR 0003](0003-receipt-reading-model.md)).
2. Make a second, separate call after reading, with the category list and only the names
   the catalog does not know.

## Decision

- A line whose normalized name matches a product gets the product's category. The model is
  not asked about it.
- The other lines go to the model in **one separate call per receipt**. The prompt holds the
  numbered categories (each with its group) and then the unknown names, each name once. The
  model answers one number per name, and the answer schema allows only the listed numbers
  and the right count. No call is made when every line is known.
- A model suggestion is stored on the line but never creates a product, so a wrong guess is
  not remembered. Only the user's correction stores a product's category (FR-13).
- A bad answer, a timeout or an error status leaves those lines without a category. The
  image is still imported. An unavailable model stops the import run, as in reading.

## Consequences

- The reading prompt and schema stay as the evaluation measured them, so ADR 0003's numbers
  still hold, and the reader can still be replaced by a vision reader.
- The first receipts cost a few seconds more, because the model writes about 2 tokens per
  unknown name. As the product list grows, the call gets shorter and then stops. A category
  in the reading answer would have cost about 4 output tokens on every line of every
  receipt, known or not.
- The category list comes first in the prompt, so its start is the same on every receipt
  and Ollama can reuse it from its prompt cache.
- A model-suggested line stays unlinked. If the user later corrects another line with the
  same name, the earlier line does not move (categorization spec, Out of Scope).
- The behavior is specified in the
  [categorization spec](../../specs/features/categorization.md).
