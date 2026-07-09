# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
  highlighted, families kept whole, apply with confirm and Stop.
- Terminal transparency: a quiet >_ toggle reveals each action's
  exact CLI command with Copy, and confirmation dialogs carry the
  command under Show Details.
