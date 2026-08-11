"""Default-off CLI for the compact Stage 4D v0.4 development run."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.llm_extraction import openai_development_run_v0_4 as run
from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequestV04,
    LLMProviderResponse,
    ValidatedCandidateOutput,
)
from document_intelligence.llm_extraction.errors import Stage4BError


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        self.exit(
            2,
            '{"error_code":"invalid_cli_arguments",'
            '"message":"Invalid command-line arguments"}\n',
        )


def _parser() -> argparse.ArgumentParser:
    parser = _SanitizedArgumentParser(
        description=(
            "Report offline v0.4 development readiness, or execute only after "
            "an exact project-owner authorization and explicit real-mode gate."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--authorization-json", type=Path)
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
    documents: Mapping[str, ParsedDocument] | None = None,
    repository_head_sha: str | None = None,
    clock: Callable[[], datetime] | None = None,
    api_key_reader: Callable[[], str | None] | None = None,
    client_factory: Callable[[str], object] | None = None,
    provider_call: Callable[
        [object, LLMExtractionRequestV04], LLMProviderResponse
    ]
    | None = None,
    local_validator: Callable[
        [LLMExtractionRequestV04, LLMProviderResponse], ValidatedCandidateOutput
    ]
    | None = None,
) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if not arguments.execute_real_development:
            readiness = run.prepare_development_run_v0_4(
                repository_root=arguments.repository_root,
                repository_head_sha=repository_head_sha,
                documents=documents,
            )
            _emit(
                {
                    "mode": "readiness",
                    "status": "offline_ready_for_independent_review",
                    "run_spec": readiness.spec.model_dump(mode="json"),
                }
            )
            return 0

        keywords: dict[str, object] = {
            "repository_root": arguments.repository_root,
            "authorization_path": arguments.authorization_json,
            "execute_real_development": True,
            "confirmation": arguments.confirmation,
            "repository_head_sha": repository_head_sha,
            "documents": documents,
        }
        if clock is not None:
            keywords["clock"] = clock
        if api_key_reader is not None:
            keywords["api_key_reader"] = api_key_reader
        if client_factory is not None:
            keywords["client_factory"] = client_factory
        if provider_call is not None:
            keywords["provider_call"] = provider_call
        if local_validator is not None:
            keywords["local_validator"] = local_validator
        result = run.execute_development_run_v0_4(**keywords)  # type: ignore[arg-type]
        _emit(
            {
                "execution_id": result.readiness.spec.execution_id,
                "execution_record": result.execution_record_path.relative_to(
                    result.readiness.repository_root
                ).as_posix(),
                "mode": "real_execution",
                "provider_call_count": result.provider_call_count,
                "status": "passed",
            }
        )
        return 0
    except Stage4BError as error:
        _emit(
            {"error_code": error.code.value, "message": error.message},
            error=True,
        )
        return 2
    except Exception:
        _emit(
            {
                "error_code": "execution_failed",
                "message": "bounded v0.4 development command failed",
            },
            error=True,
        )
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
