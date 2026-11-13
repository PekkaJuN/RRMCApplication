"""Finnish order of names (archiving spec P1): the archive has no catalog order."""

# By code point ä comes before å, so the three letters are mapped to the characters right
# after z, in the Finnish alphabet's order å, ä, ö.
_FINNISH = str.maketrans({"å": "{", "ä": "|", "ö": "}"})


def finnish_key(name: str) -> tuple[str, str]:
    """Sort key: case-insensitive, å, ä and ö after z; ties broken by the exact name."""
    return name.casefold().translate(_FINNISH), name
