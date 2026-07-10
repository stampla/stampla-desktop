# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Files excluded by import ignore patterns are counted in the Organize
  summary, and a folder where every file is excluded says so explicitly
  in Organize and Import instead of rendering as empty.

### Changed

- Groups replace families throughout, matching stampla 0.2
  vocabulary; requires stampla >= 0.2.

### Added

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
