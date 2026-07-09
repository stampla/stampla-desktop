"""Build a small throwaway archive for trying the GUI (macOS: needs sips).

Stages a few dated JPEGs as a pretend memory card, imports them through the
real engine (so History has a journal), then plants one date edit, one
unnamed file and one orphan sidecar so every screen has something to show.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "archive"
CARD = HERE / "card"
CONFIG = HERE / "demo.toml"

PHOTOS = [
    ("IMG_0001.jpg", (188, 132, 84), "2026:07:03 15:07:27"),
    ("IMG_0002.jpg", (96, 148, 122), "2026:07:03 15:09:41"),
    ("IMG_0003.jpg", (74, 96, 138), "2026:07:04 09:12:03"),
    ("IMG_0007.jpg", (142, 90, 104), "2025:12:24 17:30:15"),
]


def png_bytes(rgb: tuple[int, int, int]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    width = height = 64
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def make_jpeg(path: Path, rgb: tuple[int, int, int], date: str) -> None:
    png = path.with_suffix(".png")
    png.write_bytes(png_bytes(rgb))
    subprocess.run(
        ["sips", "-s", "format", "jpeg", str(png), "--out", str(path)],
        check=True,
        capture_output=True,
    )
    png.unlink()
    subprocess.run(
        ["exiftool", "-overwrite_original", f"-DateTimeOriginal={date}", str(path)],
        check=True,
        capture_output=True,
    )


def month_dir(date: str) -> Path:
    year, month = date[:4], date[5:7]
    return ARCHIVE / "Photos" / year / f"{year}-{month}"


def main() -> None:
    for directory in (ARCHIVE, CARD):
        if directory.exists():
            shutil.rmtree(directory)
    CARD.mkdir(parents=True)
    (ARCHIVE / "Photos").mkdir(parents=True)
    for name, rgb, date in PHOTOS:
        make_jpeg(CARD / name, rgb, date)

    CONFIG.write_text(
        f'root = "{ARCHIVE}"\n\n[[trees]]\npath = "Photos"\nmedia = "photo"\n'
        'layout = "{yyyy}/{yyyy}-{mm}"\n'
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "stampla",
            "import",
            str(CARD),
            "--config",
            str(CONFIG),
            "--apply",
        ],
        check=True,
    )

    # Plant work for the GUI to find: a corrected date, an unnamed file,
    # and a sidecar whose master is gone.
    converged = sorted(month_dir("2026:07").glob("2026*.jpg"))[0]
    subprocess.run(
        ["exiftool", "-overwrite_original", "-DateTimeOriginal+=0:0:0 2:0:0", str(converged)],
        check=True,
        capture_output=True,
    )
    make_jpeg(month_dir("2026:07") / "IMG_0042.jpg", (60, 120, 60), "2026:07:05 11:22:33")
    (month_dir("2026:07") / "20260101_000000_deadbeef.xmp").write_text(
        "<x:xmpmeta xmlns:x='adobe:ns:meta/'/>\n"
    )

    print(f"\ndemo archive ready: {ARCHIVE}\nrun: stampla-desktop {CONFIG}")


if __name__ == "__main__":
    main()
