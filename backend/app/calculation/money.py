"""The limit of a typed amount in integer cents (NFR-6)."""

# ±999 999,99 €: far above any receipt, and exact as a JavaScript number in the UI.
AMOUNT_LIMIT = 99_999_999
