"""Refuse to run tests next to real data (specs/features/test-isolation.md, PC5).

The app's `backend` service mounts the receipt folders and the database volume under `/data`.
The `backend-test` service has an empty temporary `/data` with nothing mounted under it.
Any mount under `/data` counts, so this check needs no list of folder names.
"""

import re

DATA_ROOT = "/data"
SAFE_COMMAND = "docker compose run --rm backend-test pytest"

# /proc/self/mounts writes space, tab, newline and backslash in octal, e.g. \040.
_OCTAL_ESCAPE = re.compile(r"\\([0-7]{3})")


def _decode(field: str) -> str:
    return _OCTAL_ESCAPE.sub(lambda match: chr(int(match.group(1), 8)), field)


def find_real_data_mount(mounts: str) -> str | None:
    """Return the first mount point in `mounts` that may hold real data, or None.

    `mounts` is the text of /proc/self/mounts. A mount under /data counts, and so does /data
    itself unless it is a tmpfs.
    """
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        mount_point, fs_type = _decode(fields[1]), fields[2]
        if mount_point == DATA_ROOT and fs_type != "tmpfs":
            return mount_point
        if mount_point.startswith(DATA_ROOT + "/"):
            return mount_point
    return None


def refusal_line(mount_point: str) -> str:
    """Return the one line printed when tests refuse to run. It names only the mount point."""
    return f"Refusing to run tests: real data may be mounted at {mount_point}. Use: {SAFE_COMMAND}"
