"""Tests for the palette and stylesheet."""

from __future__ import annotations

from stampla_desktop import theme


def test_every_token_is_substituted() -> None:
    assert "%(" not in theme.QSS


def test_palette_colors_are_hex() -> None:
    for name, value in theme.PALETTE.items():
        assert value.startswith("#"), name


def test_accent_reaches_the_stylesheet() -> None:
    assert theme.PALETTE["amber"] in theme.QSS
