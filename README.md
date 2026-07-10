# Stampla Desktop

[![CI](https://github.com/stampla/stampla-desktop/actions/workflows/ci.yml/badge.svg)](https://github.com/stampla/stampla-desktop/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/stampla-desktop)](https://pypi.org/project/stampla-desktop/)

The desktop app for photo and video archives that can prove their own
integrity: import memory cards, check the archive's health, fix names,
undo anything — every action a preview first.

Stampla names every photo and video after an identity derived
purely from the file itself — the capture time plus a fingerprint of
the content:

```
20260703_150727_9b677b64.nef
└──────┬──────┘ └──┬───┘
  capture time    hash
```

There is no database to maintain or lose: the files carry their own
catalog. Names sort chronologically across every camera and phone,
duplicates identify themselves, and the whole archive can be re-checked
at any time — corruption told apart from ordinary edits — with any tool
that can hash a file, decades from now.

The app covers the whole workflow:

- **Import** copies a card into the archive, names every file on
  arrival, and re-hashes every copy at its destination. It ends in a
  verdict, not a guess: *safe to format* appears only when every file
  on the card is accounted for.
- **Organize** triages a messy folder — what each file would become,
  what is already archived, what needs your eyes first — and never
  renames anything.
- **Verify** recomputes every name from metadata and content and
  explains disagreements in plain language, worst first.
- **Rename** brings names in line after edits, whole groups (RAW,
  sidecars, derivatives) at a time. Masters managed by Lightroom
  Classic are handed off through a rename token, never touched behind
  the catalog's back.
- **History** lists every applied change with Undo, and Resume for
  interrupted runs.
- **Settings** edits the archive configuration with validation before
  every save; the naming pattern editor previews an example name as
  you type.

![The Import view after copying a card: a green banner reads "Card fully accounted for — safe to format", above the list of copied files with their new names.](https://raw.githubusercontent.com/stampla/stampla-desktop/main/docs/import.png)

![The Verify view: findings grouped by meaning with plain-language explanations — a date disagreement shown with the old time in red and the corrected time in green.](https://raw.githubusercontent.com/stampla/stampla-desktop/main/docs/verify.png)

The app adds no behavior of its own: every view renders the plans and
reports of the [stampla](https://github.com/stampla/stampla)
library — the same engine behind the CLI — and every change goes
through its validated, write-ahead-journaled apply. The exact terminal
equivalent of any action is one click away, behind the quiet `>_`
toggle.

## Install

**macOS (Apple Silicon):** download `Stampla-<version>-arm64.dmg`
from [Releases](https://github.com/stampla/stampla-desktop/releases)
and drag the app to Applications. The build is not yet signed with an
Apple Developer ID, so the first launch is blocked: open **System
Settings → Privacy & Security**, scroll to Security and click
**Open Anyway**. This is needed once.

**Any platform (Python 3.11+):**

```console
$ uv tool install stampla-desktop
```

or `pipx install stampla-desktop`. Either way you also need
[ExifTool](https://exiftool.org/) on `PATH` (macOS:
`brew install exiftool`).

## Run

```console
$ stampla-desktop [archive.toml]
```

Without an argument the app asks for an archive configuration and
remembers it — or creates a new archive from scratch. Everything is a
dry run until Apply, which confirms first; every applied change lands
in History with Undo.

## Run from this repository

With [uv](https://docs.astral.sh/uv/):

```console
$ git clone https://github.com/stampla/stampla-desktop.git
$ cd stampla-desktop
$ uv run stampla-desktop
```

With plain pip:

```console
$ python3 -m venv .venv
$ .venv/bin/pip install -e .
$ .venv/bin/stampla-desktop
```

For a tour that touches none of your own files, generate the demo
archive (macOS only — it leans on `sips`): a small throwaway archive
imported through the real engine, then seeded with a date edit, an
unnamed file and an orphan sidecar so every view has something to
show:

```console
$ uv run python demo/make_demo.py
$ uv run stampla-desktop demo/demo.toml
```

Development setup, checks and expectations:
[CONTRIBUTING.md](https://github.com/stampla/stampla-desktop/blob/main/CONTRIBUTING.md).

## Requirements

- Python 3.11+ (the macOS app bundles its own)
- [ExifTool](https://exiftool.org/) on `PATH`

## License

[MIT](https://github.com/stampla/stampla-desktop/blob/main/LICENSE)
