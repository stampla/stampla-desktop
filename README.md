# Stampla Desktop

Desktop app for [Stampla](https://github.com/stampla/stampla)
photo and video archives.

The design premise: the CLI already plans everything before touching
anything, so the app is a renderer of those plans and reports — every
view is a dry run, and Apply goes through the same validated, journaled
engine. Views are named after the commands they wrap (Verify, Rename,
History), and the exact terminal equivalent of every action is one
click away.

## Status

Early development.

## Run

```console
$ stampla-desktop [archive.toml]
```

Without an argument the app asks for an archive configuration and
remembers it. Everything is a dry run until Apply, which confirms
first; every applied change lands in History with Undo (and Resume,
for interrupted runs).

## Demo archive

Builds a small throwaway archive under `demo/archive` (macOS: uses
`sips`), imports it through the real engine, then plants a date edit,
an unnamed file and an orphan sidecar so every view has something to
show:

```console
$ python demo/make_demo.py
$ stampla-desktop demo/demo.toml
```

## Requirements

- Python 3.11+
- [ExifTool](https://exiftool.org/) on `PATH`

## License

[MIT](LICENSE)
