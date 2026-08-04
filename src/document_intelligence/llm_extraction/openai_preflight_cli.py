"""CLI for local readiness or one explicitly authorized OpenAI preflight."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction import (
    openai_preflight_execution_v0_2 as execution,
)


_INVALID_EXIT_CODES = frozenset(
    {
        Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
        Stage4BErrorCode.PREFLIGHT_TERMS_INVALID,
        Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
        Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
        Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
        Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING,
        Stage4BErrorCode.PREFLIGHT_API_KEY_INVALID,
    }
)

_SANITIZED_ARGUMENT_ERROR = (
    '{"error_code":"invalid_cli_arguments",'
    '"message":"Invalid command-line arguments"}'
)


class _SanitizedArgumentParser(argparse.ArgumentParser):
    """Reject invalid syntax without reflecting arguments or their values."""

    def error(self, message: str) -> NoReturn:
        del message
        self.exit(2, f"{_SANITIZED_ARGUMENT_ERROR}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description=(
            "Validate local synthetic-preflight readiness or run the one-call "
            "transaction after explicit authorization."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument("--pricing-json", type=Path, required=True)
    parser.add_argument("--data-controls-json", type=Path, required=True)
    parser.add_argument("--execute-real-preflight", action="store_true")
    parser.add_argument("--confirmation")
    return parser


def _emit_stdout(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _emit_error(error: Stage4BError) -> None:
    print(
        json.dumps(
            {"error_code": error.code.value, "message": error.message},
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=sys.stderr,
    )


def _run_cli(
    argv: Sequence[str] | None = None,
    *,
    repository_root: Path | None = None,
    clock: Callable[[], datetime] | None = None,
    api_key_reader: Callable[[], str | None] | None = None,
    client_factory: Callable[[str], object] | None = None,
) -> int:
    """Shared private CLI flow; dependency injection is test-only."""
    arguments = _parser().parse_args(argv)
    try:
        if not arguments.execute_real_preflight:
            if repository_root is None:
                readiness = execution.validate_openai_preflight_readiness(
                    authorization_path=arguments.authorization_json,
                    pricing_path=arguments.pricing_json,
                    data_controls_path=arguments.data_controls_json,
                )
            else:
                readiness = execution._validate_openai_preflight_readiness(
                    authorization_path=arguments.authorization_json,
                    pricing_path=arguments.pricing_json,
                    data_controls_path=arguments.data_controls_json,
                    repository_root=repository_root,
                    clock=clock or (lambda: datetime.now(timezone.utc)),
                )
            _emit_stdout(
                {
                    "execution_plan_sha256": (
                        readiness.plan.execution_plan_sha256
                    ),
                    "mode": "readiness",
                    "preflight_id": readiness.plan.preflight_id,
                    "status": "ready",
                }
            )
            return 0

        if repository_root is None:
            result = execution.execute_openai_synthetic_preflight(
                authorization_path=arguments.authorization_json,
                pricing_path=arguments.pricing_json,
                data_controls_path=arguments.data_controls_json,
                execute_real_preflight=True,
                confirmation=arguments.confirmation,
            )
        else:
            result = execution._execute_openai_synthetic_preflight_transaction(
                authorization_path=arguments.authorization_json,
                pricing_path=arguments.pricing_json,
                data_controls_path=arguments.data_controls_json,
                repository_root=repository_root,
                execute_real_preflight=True,
                confirmation=arguments.confirmation,
                clock=clock or (lambda: datetime.now(timezone.utc)),
                api_key_reader=(
                    api_key_reader or execution._openai_api_key_from_environment
                ),
                client_factory=(
                    client_factory or execution._production_openai_client_factory
                ),
            )
        _emit_stdout(
            {
                "execution_plan_sha256": result.plan.execution_plan_sha256,
                "mode": "real_execution",
                "preflight_id": result.plan.preflight_id,
                "preflight_record_sha256": result.record.preflight_record_sha256,
                "status": "passed",
            }
        )
        return 0
    except Stage4BError as error:
        _emit_error(error)
        return 2 if error.code in _INVALID_EXIT_CODES else 1
    except Exception:
        _emit_error(
            Stage4BError(
                Stage4BErrorCode.EXECUTION_FAILED,
                "OpenAI synthetic preflight command failed",
            )
        )
        return 1


def _main_for_tests(
    argv: Sequence[str] | None = None,
    *,
    repository_root: Path,
    clock: Callable[[], datetime] | None = None,
    api_key_reader: Callable[[], str | None] | None = None,
    client_factory: Callable[[str], object] | None = None,
) -> int:
    """Run the offline CLI flow with a private temporary-repository boundary."""
    return _run_cli(
        argv,
        repository_root=repository_root,
        clock=clock,
        api_key_reader=api_key_reader,
        client_factory=client_factory,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run only against the verified installed checkout and fixed artifacts."""
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
