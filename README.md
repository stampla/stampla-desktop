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

## Requirements

- Python 3.11+
- [ExifTool](https://exiftool.org/) on `PATH`

## License

[MIT](LICENSE)
