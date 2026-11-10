from tests.data_guard import find_real_data_mount, refusal_line

# Lines in the format of /proc/self/mounts: device, mount point, type, options, 0, 0.
APP_LINE = "C:\\134 /app 9p rw,relatime 0 0"
TMPFS_DATA = "tmpfs /data tmpfs rw,nosuid,nodev,noexec,relatime 0 0"
VOLUME_DB = "/dev/sdd /data/db ext4 rw,relatime 0 0"
BIND_IMPORT = "C:\\134 /data/import 9p rw,relatime 0 0"


def test_ac7_database_volume_is_found() -> None:
    # Given a mount table with the database volume at /data/db
    mounts = "\n".join([APP_LINE, VOLUME_DB])

    # When the check runs
    # Then it names /data/db
    assert find_real_data_mount(mounts) == "/data/db"


def test_ac7_import_folder_is_found() -> None:
    mounts = "\n".join([APP_LINE, BIND_IMPORT])

    assert find_real_data_mount(mounts) == "/data/import"


def test_ac7_refusal_line_names_mount_and_safe_command() -> None:
    line = refusal_line("/data/db")

    assert line == (
        "Refusing to run tests: real data may be mounted at /data/db. "
        "Use: docker compose run --rm backend-test pytest"
    )
    assert "\n" not in line


def test_ac8_tmpfs_data_is_isolated() -> None:
    # Given /data is a temporary filesystem with nothing mounted under it
    mounts = "\n".join([APP_LINE, TMPFS_DATA])

    # Then the check finds nothing
    assert find_real_data_mount(mounts) is None


def test_ac8_no_data_mount_is_isolated() -> None:
    assert find_real_data_mount(APP_LINE + "\n") is None


def test_ac7_data_that_is_not_tmpfs_is_found() -> None:
    mounts = "\n".join([APP_LINE, "/dev/sdd /data ext4 rw,relatime 0 0"])

    assert find_real_data_mount(mounts) == "/data"


def test_ac7_mount_under_tmpfs_data_is_found() -> None:
    mounts = "\n".join([APP_LINE, TMPFS_DATA, VOLUME_DB])

    assert find_real_data_mount(mounts) == "/data/db"


def test_ac7_escaped_mount_point_is_decoded() -> None:
    # Given a mount point with a space, written as \040 in the mount table
    mounts = "C:\\134 /data/my\\040folder 9p rw 0 0"

    assert find_real_data_mount(mounts) == "/data/my folder"


def test_ac7_short_and_empty_lines_are_skipped() -> None:
    # Given a table with an empty line and a line without a type before the data volume
    mounts = "\n".join(["", "broken /data", VOLUME_DB])

    # Then the incomplete lines are skipped and the volume is still found
    assert find_real_data_mount(mounts) == "/data/db"


def test_ac7_similar_prefix_is_not_data() -> None:
    mounts = "/dev/sdd /database ext4 rw 0 0"

    assert find_real_data_mount(mounts) is None


def test_ac9_refusal_line_names_no_file() -> None:
    # Given a mount table and a folder that holds files
    mounts = "\n".join([APP_LINE, BIND_IMPORT])
    mount_point = find_real_data_mount(mounts)
    assert mount_point is not None

    # When the line is built
    line = refusal_line(mount_point)

    # Then it holds the mount point and nothing below it
    assert "/data/import." in line
    assert "/data/import/" not in line
