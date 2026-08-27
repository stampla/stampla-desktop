"""Every library bucket must render — titles, colors, explanations.

The core library can grow buckets faster than this GUI pins names for
them; rendering must degrade to something readable, never a KeyError
mid-paint.
"""

from __future__ import annotations

from stampla.report import Bucket

from stampla_desktop import buckets


class TestBucketCoverage:
    def test_every_bucket_has_a_color(self) -> None:
        for bucket in Bucket:
            assert buckets.color_of(bucket) in {"crit", "warn", "info", "ok"}

    def test_every_bucket_renders_a_title(self) -> None:
        for bucket in Bucket:
            title = buckets.title_of(bucket)
            assert title
            assert "KeyError" not in title

    def test_unknown_buckets_fall_back_to_their_value(self) -> None:
        known = set(buckets.TITLE)
        for bucket in Bucket:
            if bucket not in known:
                assert buckets.title_of(bucket) == bucket.value.replace("-", " ")
