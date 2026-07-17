"""Smoke tests for the document intelligence package."""

import document_intelligence


def test_package_exposes_non_empty_version() -> None:
    """The installed package should expose a non-empty version string."""
    assert isinstance(document_intelligence.__version__, str)
    assert document_intelligence.__version__.strip()
