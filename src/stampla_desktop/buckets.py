"""Plain-language titles and explanations for report buckets.

Severity comes from the library itself (``Bucket.severity``); the GUI
only maps it to palette keys. Titles and explanations are presentation
copy, which legitimately lives here.
"""

from stampla.report import Bucket, Severity

#: library severity → palette key
SEVERITY_COLOR = {
    Severity.ALARM: "crit",
    Severity.ATTENTION: "warn",
    Severity.EXPECTED: "info",
    Severity.SAFE: "ok",
}


def color_of(bucket: Bucket) -> str:
    # a severity this build has never seen still renders — as a warning
    return SEVERITY_COLOR.get(bucket.severity, "warn")


def title_of(bucket: Bucket) -> str:
    """Presentation title; a bucket from a newer core still renders."""
    return TITLE.get(bucket, bucket.value.replace("-", " "))


def explain_of(bucket: Bucket) -> str:
    return EXPLAIN.get(bucket, "")


TITLE = {
    Bucket.CORRUPTION: "possible corruption",
    Bucket.APPLY_FAILED: "change could not be applied",
    Bucket.HASH_ERROR: "file could not be read",
    **({Bucket.SCAN_ERROR: "folder could not be scanned"} if hasattr(Bucket, "SCAN_ERROR") else {}),
    Bucket.METADATA_UNREADABLE: "metadata could not be read",
    Bucket.DATE_MISMATCH: "name disagrees with camera time",
    Bucket.UNRESOLVED_DATE: "no capture time found",
    Bucket.COLLISION: "duplicate content",
    Bucket.AMBIGUOUS_MASTER: "master exists in several formats",
    Bucket.ORPHAN_GROUP: "sidecar without its master",
    Bucket.NEEDS_SIDECAR: "needs a sidecar first",
    Bucket.OTHER_PATTERN: "named under an older pattern",
    Bucket.MTIME_DATED: "dated from file modification time",
    Bucket.NAME_DATED: "dated from the filename",
    Bucket.MALFORMED: "name almost matches the pattern",
    Bucket.EDIT_DRIFT: "edited in place (expected)",
    Bucket.UNNAMED: "not yet named",
    Bucket.TOKEN_PENDING: "rename token planned",
    Bucket.TOKEN_WRITTEN: "rename token written",
    Bucket.RENAME_PENDING: "rename planned",
    Bucket.RENAMED: "renamed",
    Bucket.ALREADY_IMPORTED: "already in the archive",
    Bucket.IGNORED: "ignored by policy",
    Bucket.MISPLACED: "in the wrong folder",
    Bucket.RELOCATE_PENDING: "move planned",
    Bucket.RELOCATED: "moved",
}

EXPLAIN = {
    Bucket.CORRUPTION: (
        "The content of a write-once camera file changed. Cameras never"
        " rewrite these — restore from a backup and compare."
    ),
    Bucket.APPLY_FAILED: (
        "Nothing was half-done: groups apply all-or-nothing. See the"
        " detail, then retry or undo from History."
    ),
    Bucket.HASH_ERROR: "The file could not be read to compute its fingerprint.",
    **(
        {
            Bucket.SCAN_ERROR: (
                "A folder could not be listed, so files under it are"
                " unaccounted for — nothing under it was checked or copied."
            )
        }
        if hasattr(Bucket, "SCAN_ERROR")
        else {}
    ),
    Bucket.METADATA_UNREADABLE: "ExifTool could not read this file's metadata.",
    Bucket.DATE_MISMATCH: (
        "Usually a date you corrected after import. Fixing renames the"
        " whole group together — see Fix Names."
    ),
    Bucket.UNRESOLVED_DATE: (
        "No usable date field, so the file is reported and never renamed."
        " Set a date in your photo app, then check again."
    ),
    Bucket.COLLISION: "Two files resolve to the same name — the content is identical.",
    Bucket.AMBIGUOUS_MASTER: "The same photo exists as more than one master format.",
    Bucket.ORPHAN_GROUP: "A sidecar whose master file is missing.",
    Bucket.NEEDS_SIDECAR: (
        "A DAM-managed RAW has no XMP sidecar to carry the rename token."
        " Save metadata from the DAM first, then retry."
    ),
    Bucket.OTHER_PATTERN: "Recognized under a previous naming scheme; pending migration.",
    Bucket.MTIME_DATED: "Modification time is hearsay — review before trusting it.",
    Bucket.NAME_DATED: "A strict year-first timestamp in the filename supplied the date.",
    Bucket.MALFORMED: "Looks like the pattern but is not quite valid.",
    Bucket.EDIT_DRIFT: (
        "Sidecars, DNG and TIFF are rewritten by editors — normal, and does not affect names."
    ),
    Bucket.UNNAMED: "Not named by Stampla yet — Import names files on arrival.",
    Bucket.TOKEN_PENDING: "Would be written on apply.",
    Bucket.TOKEN_WRITTEN: "Finish in the DAM: Read Metadata, then rename with the token.",
    Bucket.RENAME_PENDING: "Planned; nothing changed yet.",
    Bucket.RENAMED: "Done.",
    Bucket.ALREADY_IMPORTED: "Byte-identical copy already in the archive.",
    Bucket.IGNORED: "On your ignore list — review once, then it's policy.",
    Bucket.MISPLACED: (
        "The name says when this was captured, and the tree layout says"
        " where that belongs — this file is shelved somewhere else."
    ),
    Bucket.RELOCATE_PENDING: "Planned; nothing moved yet.",
    Bucket.RELOCATED: "Done.",
}
