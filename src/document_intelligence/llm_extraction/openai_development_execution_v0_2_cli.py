"""Default-deny CLI for the bounded Stage 4D v0.2 development transaction."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

from document_intelligence.llm_extraction import (
    openai_development_execution_v0_2 as execution,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)


_INVALID_EXIT_CODES = frozenset(
    {
        Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
        Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
        Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID,
        Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
        Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING,
        Stage4BErrorCode.PREFLIGHT_API_KEY_INVALID,
    }
)
_SANITIZED_ARGUMENT_ERROR = (
    '{"error_code":"invalid_cli_arguments",'
    '"message":"Invalid command-line arguments"}'
)


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        self.exit(2, f"{_SANITIZED_ARGUMENT_ERROR}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description=(
            "Validate bounded OpenAI development readiness or run the exact "
            "transaction after separate project-owner authorization."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument("--pricing-json", type=Path, required=True)
    parser.add_argument("--data-controls-json", type=Path, required=True)
    parser.add_argument("--execute-real-development", action="store_true")
    parser.add_argument("--confirmation")
    return parser


def _emit(payload: dict[str, object], *, error: bool = False) -> None:
    print(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        file=sys.stderr if error else sys.stdout,
    )


def _run_cli(
    argv: Sequence[str] | None = None,
    *,
    repository_root: Path | None = None,
    clock: Callable[[], datetime] | None = None,
    api_key_reader: Callable[[], str | None] | None = None,
    client_factory: Callable[[str], object] | None = None,
    reconstructor: execution.RequestReconstructor | None = None,
    provider_observation: execution.ProviderObservation | None = None,
    local_validator: execution.LocalValidator | None = None,
) -> int:
    arguments = _parser().parse_args(argv)
    selected_clock = clock or (lambda: datetime.now(timezone.utc))
    try:
        if not arguments.execute_real_development:
            if repository_root is None:
                readiness = execution.validate_openai_development_execution_readiness_v0_2(
                    authorization_path=arguments.authorization_json,
                    pricing_path=arguments.pricing_json,
                    data_controls_path=arguments.data_controls_json,
                )
            else:
                readiness = execution._validate_openai_development_execution_readiness_v0_2(
                    authorization_path=arguments.authorization_json,
                    pricing_path=arguments.pricing_json,
                    data_controls_path=arguments.data_controls_json,
                    repository_root=repository_root,
                    clock=selected_clock,
                    reconstructor=(
                        reconstructor or execution._reconstruct_invocations
                    ),
                )
            _emit(
                {
                    "execution_id": readiness.plan.execution_id,
                    "execution_plan_sha256": readiness.plan.execution_plan_sha256,
                    "mode": "readiness",
                    "status": (
                        "already_complete"
                        if readiness.existing_execution_record is not None
                        else "ready"
                    ),
                }
            )
            return 0

        if repository_root is None:
            result = execution.execute_openai_development_v0_2(
                authorization_path=arguments.authorization_json,
                pricing_path=arguments.pricing_json,
                data_controls_path=arguments.data_controls_json,
                execute_real_development=True,
                confirmation=arguments.confirmation,
            )
        else:
            result = execution._execute_openai_development_transaction_v0_2(
                authorization_path=arguments.authorization_json,
                pricing_path=arguments.pricing_json,
                data_controls_path=arguments.data_controls_json,
                repository_root=repository_root,
                execute_real_development=True,
                confirmation=arguments.confirmation,
                clock=selected_clock,
                api_key_reader=(
                    api_key_reader or execution._openai_api_key_from_environment
                ),
                client_factory=(
                    client_factory or execution._production_openai_client_factory
                ),
                reconstructor=(reconstructor or execution._reconstruct_invocations),
                provider_observation=(
                    provider_observation or execution._production_provider_observation
                ),
                local_validator=(local_validator or execution.validate_provider_output),
            )
        _emit(
            {
                "execution_id": result.record.execution_id,
                "execution_record_sha256": (
                    result.record.execution_record_sha256
                ),
                "mode": "real_execution",
                "provider_call_count": result.record.provider_call_count,
                "status": "passed",
            }
        )
        return 0
    except Stage4BError as error:
        _emit(
            {"error_code": error.code.value, "message": error.message},
            error=True,
        )
        return 2 if error.code in _INVALID_EXIT_CODES else 1
    except Exception:
        _emit(
            {
                "error_code": Stage4BErrorCode.EXECUTION_FAILED.value,
                "message": "bounded OpenAI development command failed",
            },
            error=True,
        )
        return 1


def _main_for_tests(
    argv: Sequence[str] | None = None,
    *,
    repository_root: Path,
    clock: Callable[[], datetime] | None = None,
    api_key_reader: Callable[[], str | None] | None = None,
    client_factory: Callable[[str], object] | None = None,
    reconstructor: execution.RequestReconstructor | None = None,
    provider_observation: execution.ProviderObservation | None = None,
    local_validator: execution.LocalValidator | None = None,
) -> int:
    return _run_cli(
        argv,
        repository_root=repository_root,
        clock=clock,
        api_key_reader=api_key_reader,
        client_factory=client_factory,
        reconstructor=reconstructor,
        provider_observation=provider_observation,
        local_validator=local_validator,
    )


def main(argv: Sequence[str] | None = None) -> int:
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
