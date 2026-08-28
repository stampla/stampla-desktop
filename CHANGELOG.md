# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-28

### Fixed

- Archive configurations created on Windows load: the default config
  wrote the archive path with backslashes, which are escape sequences
  inside a TOML string — every Windows-created config failed to parse.
- The app finds ExifTool when launched from the Finder: a Finder
  launch inherits the system's minimal PATH, so a Homebrew or MacPorts
  install read as missing; the usual install prefixes are probed at
  startup.
- The packaged app no longer risks relaunching itself once per hash
  worker (multiprocessing freeze support in the frozen bundle).
- Closing the window mid-operation stops the work at the library's
  next safe point first, instead of killing it mid-apply and leaving
  the archive lock behind; a dialog offers Stop and close.
- One operation at a time across all views: a second Preview, Apply,
  Undo or Analyze anywhere is refused while one runs, instead of
  fighting over the archive lock after minutes of planning. The
  import source cannot be swapped mid-run, and the verdict banner
  names the source it speaks for.
- Undo and Resume in History show live progress with a Stop button,
  refuse double-clicks before the confirm dialog, and their failures —
  like every failed apply — open a dialog with the full error text
  instead of one truncated status-bar line.
- Stopping a token write no longer claims "a preview changes nothing";
  written tokens are acknowledged and the pending card is replaced,
  not stacked, after a write.
- Settings refuses to save over a config edited on disk since the
  form was loaded — Reload first — instead of silently overwriting
  the external change.
- The History panel's terminal command for undoing teaches the
  archive-scoped journal path; a bare `undo --latest` reaches across
  every archive on the machine.
- Findings render for report buckets this build has never seen
  (titles and colors fall back), so a newer library cannot crash a
  view mid-paint; the `scan-error` alarm from stampla 0.5 is rendered
  with its own title and explanation. Requires stampla >= 0.5.

## [0.2.0] - 2026-07-11

### Added

- Relocate view: files whose name says they belong in another folder
  are moved there through the journaled engine, whole groups at a
  time — with the DAM folder checklist rendered as "Do this inside
  Lightroom" and shoot-filed trees reported, never guessed. Requires
  stampla >= 0.4.
- Shoot on Import: a shoot/job field fills the {shoot} layout token
  for trees that file by shoot; it appears only when one does, and
  the CLI panel mirrors it as --shoot.
- Naming pattern editor in Settings: timestamp shape, separator, digest
  algorithm and length, and image-data hashing are editable with a live
  example name that surfaces the library's own validation (sortability,
  filename safety, the DAM token cap). Saving a changed pattern requires
  a new pattern name, keeps the old scheme recognized under additional
  patterns, and explains the migration before writing anything; nothing
  is renamed by saving. Requires stampla >= 0.3.

### Fixed

- The Trees help no longer advertises the {shoot} layout token, which
  is not part of the released library.

## [0.1.0] - 2026-07-10

### Fixed

- Files excluded by import ignore patterns are counted in the Organize
  summary, and a folder where every file is excluded says so explicitly
  in Organize and Import instead of rendering as empty.

### Changed

- Groups replace families throughout, matching stampla 0.2
  vocabulary; requires stampla >= 0.2.
- Depends on PySide6-Essentials instead of the full PySide6
  metapackage — the app uses no Addons module, and the packaged
  bundle is roughly half the size.

### Added

- App icon: an aperture iris with clock hands in the opening, drawn
  from geometry at every size (small sizes are redrawn bolder, not
  downscaled).
- macOS app bundle: releases attach an Apple Silicon .dmg built with
  PyInstaller; the bundle is ad-hoc signed until there is a Developer
  ID, and the README documents the one-time Open Anyway step.
- Dark theme: graphite palette with a safelight-amber accent.
- Background worker: library calls run off the UI thread with
  throttled progress events and a cooperative stop flag.
- Application shell: archive-centric window with a sidebar of views
  and an Overview of the archive and its trees.
- Verify view: findings in library order colored by library severity,
  plain-language explanations, structured date-mismatch details, live
  progress and Stop.
- History view: every run against the archive with its originating
  command, timestamp and status; Undo for applied runs, Resume for
  interrupted ones.
- Rename view: the plan as old → new with the changed span
  highlighted, groups kept whole, apply with confirm and Stop.
- Terminal transparency: a quiet >_ toggle reveals each action's
  exact CLI command with Copy, and confirmation dialogs carry the
  command under Show Details.
- Demo archive generator for a safe tour of every view.
- Import view: card to archive with live progress, problem list and
  the safe-to-format verdict — green only when the library itself
  issues it.
- Organize view: report-only triage of messy folders with a hand-off
  to Import for confirmed batches.
- DAM hand-off in the Rename view: masters the DAM must rename itself
  are listed with their tokens and the in-DAM checklist; writing tokens
  is its own confirmed action, verified by reading each token back.
- Hardening for huge archives: capped rendering with exact counts
  everywhere, accurate post-apply import summaries (failed groups are
  never reported as copied), History capped and guarded against
  double-clicks.
- Settings view: edit the archive configuration with validation before
  every save and hand-written comments preserved; the naming pattern is
  shown read-only. First-run flow can create a new archive config.
- Design pass: one clean surface per card (no label striping), sidebar
  wordmark, empty states on every action view, tinted verdict banner,
  severity stripes, status pills, calm undo, styled form controls, and
  per-view status messages that can no longer go stale.
