"""Deterministic utilities for technical PDF corpus audits."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from document_intelligence.audit.pdf_audit import (
        PdfAuditResult,
        audit_directory,
        audit_pdf,
    )

__all__ = ["PdfAuditResult", "audit_directory", "audit_pdf"]


def __getattr__(name: str) -> Any:
    """Load public PDF-audit attributes only when they are requested."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from document_intelligence.audit import pdf_audit

    return getattr(pdf_audit, name)
