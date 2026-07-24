"""Command-line audit summary for guarded development public-gold access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessError,
    BaselineGoldAccessMode,
    DevelopmentGoldSummary,
    load_baseline_gold,
    summarize_development_gold,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize guarded deterministic-baseline gold access."
    )
    parser.add_argument(
        "--repository-root",
        required=True,
        type=Path,
        help="Explicit repository root containing the frozen experiment and annotations.",
    )
    parser.add_argument(
        "--access",
        choices=[mode.value for mode in BaselineGoldAccessMode],
        default=BaselineGoldAccessMode.DEVELOPMENT.value,
        help="Access mode; held_out is intentionally denied in Stage 3B.2.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path for the same deterministic non-semantic summary JSON.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow replacement of an existing report file.",
    )
    return parser


def _canonical_summary_json(summary: DevelopmentGoldSummary) -> str:
    payload = summary.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_report(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise BaselineGoldAccessError(
            "report already exists; use --force to overwrite it"
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as error:
        raise BaselineGoldAccessError("report could not be written") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Run the guarded loader and emit only deterministic summary JSON."""
    args = _build_parser().parse_args(argv)
    try:
        bundle = load_baseline_gold(
            repository_root=args.repository_root,
            access_mode=BaselineGoldAccessMode(args.access),
        )
        summary = summarize_development_gold(bundle)
        content = _canonical_summary_json(summary)
        if args.report is not None:
            _write_report(args.report, content, force=args.force)
    except (BaselineGoldAccessError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
