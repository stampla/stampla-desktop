# Contributing

## Development setup

```console
$ python3 -m venv .venv
$ .venv/bin/pip install -e ".[dev]"
```

To develop against a local `stampla` checkout (changing library
and app in lockstep), install it editable first:

```console
$ .venv/bin/pip install -e ../stampla -e ".[dev]"
```

[ExifTool](https://exiftool.org/) must be on `PATH`; integration tests
skip without it, but CI always runs them. Tests run Qt headless
(`QT_QPA_PLATFORM=offscreen`); no display is needed.

## Checks

Everything CI runs, locally:

```console
$ ruff format --check .
$ ruff check .
$ mypy
$ pytest --cov=stampla_desktop
```

## Expectations

- Every change ships with tests and any needed documentation in the same
  commit.
- The app adds no behavior of its own: every screen renders the
  library's plans and reports, and every mutation goes through the same
  validated, journaled engine as the CLI. Treat a change that would
  bypass that as a design discussion, not a patch.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`, `chore:`).
