"""Offline CLI tests for the Stage 4D-3A synthetic-preflight gate."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import document_intelligence.llm_extraction.openai_preflight_cli as cli
import document_intelligence.llm_extraction.openai_preflight_execution as execution
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.prompting import canonical_json_bytes


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
FICTIONAL_KEY = "fictional-cli-key"


def _write(path: Path, model: object) -> None:
    path.write_bytes(
        canonical_json_bytes(model.model_dump(mode="json"))  # type: ignore[attr-defined]
    )


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    authorization = tmp_path / "authorization.json"
    pricing = tmp_path / "pricing.json"
    controls = tmp_path / "controls.json"
    _write(
        authorization,
        OpenAIPreflightAuthorization(
            authorization_id="fictional-cli-authorization",
            authorized_by="Fictional CLI Owner",
            authorized_at_utc=NOW - timedelta(minutes=5),
            scope=PREFLIGHT_AUTHORIZATION_SCOPE,
            maximum_provider_calls=1,
            real_provider_preflight_authorized=True,
        ),
    )
    _write(
        pricing,
        OpenAIPricingObservation(
            observed_at_utc=NOW,
            source_title="Fictional CLI pricing",
            source_url="https://example.invalid/pricing",
            input_usd_per_million_tokens=Decimal("1.25"),
            output_usd_per_million_tokens=Decimal("5.50"),
            currency="USD",
        ),
    )
    _write(
        controls,
        OpenAIDataControlsObservation(
            observed_at_utc=NOW,
            source_title="Fictional CLI controls",
            source_url="https://example.invalid/controls",
            store_false_required=True,
            zero_retention_claimed=False,
            retention_and_abuse_monitoring_summary="Fictional limitations apply.",
        ),
    )
    return authorization, pricing, controls


def _arguments(paths: tuple[Path, Path, Path]) -> list[str]:
    return [
        "--authorization-json",
        str(paths[0]),
        "--pricing-json",
        str(paths[1]),
        "--data-controls-json",
        str(paths[2]),
    ]


def _fictional_project_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "fictional-project-checkout"
    (root / ".git").mkdir(parents=True)
    source = (
        root
        / "src"
        / "document_intelligence"
        / "llm_extraction"
        / "openai_preflight_execution.py"
    )
    source.parent.mkdir(parents=True)
    source.write_text("# fictional installed source identity\n", encoding="utf-8")
    prompt_root = source.parent / "prompts"
    prompt_root.mkdir()
    (prompt_root / "system_v0_1.txt").write_text("fictional system\n", encoding="utf-8")
    (prompt_root / "extraction_v0_1.txt").write_text(
        "fictional extraction\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "llm-document-intelligence-pipeline"\n'
        "[project.scripts]\n"
        "run-openai-synthetic-preflight = "
        '"document_intelligence.llm_extraction.openai_preflight_cli:main"\n',
        encoding="utf-8",
        newline="\n",
    )
    return root


def _raw_output() -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-cli-batch",
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class FakeSDKResponse:
    status = "completed"
    model = "gpt-5.4-mini-fictional-cli"
    id = "resp_fictional_cli"
    _request_id = "req_fictional_cli"
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    output = (
        SimpleNamespace(
            type="message",
            content=(SimpleNamespace(type="output_text", text=_raw_output()),),
        ),
    )

    def model_dump(self, *, mode: str) -> dict[str, str]:
        return {"id": self.id, "model": self.model}


class FakeResponses:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: object) -> None:
        self.responses = FakeResponses(outcome)

    def with_options(self, *, max_retries: int, timeout: float):
        return self


def test_readiness_cli_returns_zero_without_secret_client_or_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _paths(tmp_path)

    code = cli._main_for_tests(
        _arguments(paths),
        repository_root=tmp_path,
        clock=lambda: NOW,
        api_key_reader=lambda: (_ for _ in ()).throw(
            AssertionError("readiness must not read the environment")
        ),
        client_factory=lambda key: (_ for _ in ()).throw(
            AssertionError("readiness must not construct a client")
        ),
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload == {
        "execution_plan_sha256": (
            execution.build_openai_preflight_execution_plan().execution_plan_sha256
        ),
        "mode": "readiness",
        "preflight_id": execution.PREFLIGHT_ID,
        "status": "ready",
    }
    assert captured.err == ""
    assert not tmp_path.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()


@pytest.mark.parametrize("launch_from_subdirectory", (False, True))
def test_production_cli_resolves_verified_repository_root_or_subdirectory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    launch_from_subdirectory: bool,
) -> None:
    root = _fictional_project_checkout(tmp_path)
    paths = _paths(root)
    launch = root
    if launch_from_subdirectory:
        launch = root / "docs" / "nested"
        launch.mkdir(parents=True)
    monkeypatch.chdir(launch)
    monkeypatch.setattr(execution, "_installed_repository_root", lambda: root)

    monkeypatch.setattr(execution, "_utc_now", lambda: NOW)
    monkeypatch.setattr(
        execution,
        "_openai_api_key_from_environment",
        lambda: (_ for _ in ()).throw(
            AssertionError("readiness must not read a key")
        ),
    )
    monkeypatch.setattr(
        execution,
        "_production_openai_client_factory",
        lambda key: (_ for _ in ()).throw(
            AssertionError("readiness must not construct a client")
        ),
    )

    code = cli.main(_arguments(paths))

    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out)["status"] == "ready"
    assert captured.err == ""
    assert not root.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()


def test_unrelated_launch_directory_fails_before_inputs_secret_or_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fictional_project_checkout(tmp_path)
    paths = _paths(root)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setattr(execution, "_installed_repository_root", lambda: root)
    monkeypatch.setattr(
        execution,
        "_load_openai_preflight_inputs",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("root failure must precede input loading")
        ),
    )

    monkeypatch.setattr(
        execution,
        "_openai_api_key_from_environment",
        lambda: (_ for _ in ()).throw(
            AssertionError("root failure must precede secret access")
        ),
    )
    monkeypatch.setattr(
        execution,
        "_production_openai_client_factory",
        lambda key: (_ for _ in ()).throw(
            AssertionError("root failure must precede client construction")
        ),
    )

    code = cli.main(
        [
            *_arguments(paths),
            "--execute-real-preflight",
            "--confirmation",
            execution.EXECUTION_CONFIRMATION,
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert json.loads(captured.err)["error_code"] == (
        "preflight_execution_gate_invalid"
    )
    assert captured.out == ""
    assert not root.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()


def test_marker_blocks_same_repository_execution_from_another_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fictional_project_checkout(tmp_path)
    paths = _paths(root)
    subdirectory = root / "docs"
    subdirectory.mkdir()
    monkeypatch.setattr(execution, "_installed_repository_root", lambda: root)
    monkeypatch.setattr(execution, "_utc_now", lambda: NOW)
    client = FakeClient(FakeSDKResponse())
    monkeypatch.setattr(
        execution, "_openai_api_key_from_environment", lambda: FICTIONAL_KEY
    )
    monkeypatch.setattr(
        execution, "_production_openai_client_factory", lambda key: client
    )
    arguments = [
        *_arguments(paths),
        "--execute-real-preflight",
        "--confirmation",
        execution.EXECUTION_CONFIRMATION,
    ]
    monkeypatch.chdir(root)

    first = cli.main(arguments)
    first_output = capsys.readouterr()
    monkeypatch.chdir(subdirectory)
    monkeypatch.setattr(
        execution,
        "_openai_api_key_from_environment",
        lambda: (_ for _ in ()).throw(
            AssertionError("existing marker must block secret access")
        ),
    )
    monkeypatch.setattr(
        execution,
        "_production_openai_client_factory",
        lambda key: (_ for _ in ()).throw(
            AssertionError("existing marker must block client construction")
        ),
    )
    second = cli.main(arguments)

    second_output = capsys.readouterr()
    marker = root.joinpath(*execution.ATTEMPT_MARKER_RELATIVE_PATH.parts)
    assert first == 0
    assert json.loads(first_output.out)["status"] == "passed"
    assert second == 2
    assert json.loads(second_output.err)["error_code"] == (
        "preflight_attempt_already_exists"
    )
    assert marker.is_file()
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    "invalid_mutation",
    (
        b"not-json",
        b"[]",
        b'{"duplicate":1,"duplicate":2}',
    ),
)
def test_invalid_cli_input_returns_two_with_typed_sanitized_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    invalid_mutation: bytes,
) -> None:
    paths = _paths(tmp_path)
    paths[0].write_bytes(invalid_mutation)

    code = cli._main_for_tests(
        _arguments(paths),
        repository_root=tmp_path,
        clock=lambda: NOW,
    )

    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert code == 2
    assert captured.out == ""
    assert error["error_code"] == "preflight_input_file_invalid"
    assert FICTIONAL_KEY not in captured.err


@pytest.mark.parametrize(
    "confirmation",
    (None, "wrong", execution.EXECUTION_CONFIRMATION.lower()),
)
def test_invalid_real_confirmation_returns_two_before_secret_read(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    confirmation: str | None,
) -> None:
    paths = _paths(tmp_path)
    arguments = [*_arguments(paths), "--execute-real-preflight"]
    if confirmation is not None:
        arguments.extend(("--confirmation", confirmation))

    code = cli._main_for_tests(
        arguments,
        repository_root=tmp_path,
        clock=lambda: NOW,
        api_key_reader=lambda: (_ for _ in ()).throw(
            AssertionError("invalid confirmation must not read a key")
        ),
    )

    captured = capsys.readouterr()
    assert code == 2
    assert json.loads(captured.err)["error_code"] == (
        "preflight_execution_gate_invalid"
    )


def test_fake_execution_failure_returns_one_and_sanitizes_secret_exception(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _paths(tmp_path)
    arguments = [
        *_arguments(paths),
        "--execute-real-preflight",
        "--confirmation",
        execution.EXECUTION_CONFIRMATION,
    ]

    def failed_factory(key: str) -> object:
        raise RuntimeError(f"must not leak {key}")

    code = cli._main_for_tests(
        arguments,
        repository_root=tmp_path,
        clock=lambda: NOW,
        api_key_reader=lambda: FICTIONAL_KEY,
        client_factory=failed_factory,
    )

    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert code == 1
    assert captured.out == ""
    assert error["error_code"] == "execution_failed"
    assert FICTIONAL_KEY not in captured.err


def test_valid_fake_real_cli_returns_only_safe_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _paths(tmp_path)
    client = FakeClient(FakeSDKResponse())

    code = cli._main_for_tests(
        [
            *_arguments(paths),
            "--execute-real-preflight",
            "--confirmation",
            execution.EXECUTION_CONFIRMATION,
        ],
        repository_root=tmp_path,
        clock=lambda: NOW,
        api_key_reader=lambda: FICTIONAL_KEY,
        client_factory=lambda key: client,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["mode"] == "real_execution"
    assert payload["status"] == "passed"
    assert set(payload) == {
        "execution_plan_sha256",
        "mode",
        "preflight_id",
        "preflight_record_sha256",
        "status",
    }
    assert captured.err == ""
    assert FICTIONAL_KEY not in captured.out
    assert _raw_output() not in captured.out
    assert len(client.responses.calls) == 1


def _assert_sanitized_parse_failure(
    arguments: list[str],
    repository_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as captured:
        cli._main_for_tests(
            arguments,
            repository_root=repository_root,
            clock=lambda: NOW,
        )

    output = capsys.readouterr()
    assert captured.value.code == 2
    assert output.out == ""
    assert json.loads(output.err) == {
        "error_code": "invalid_cli_arguments",
        "message": "Invalid command-line arguments",
    }
    assert FICTIONAL_KEY not in output.out
    assert FICTIONAL_KEY not in output.err


def test_all_required_paths_plus_api_key_are_rejected_without_echo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _assert_sanitized_parse_failure(
        [*_arguments(_paths(tmp_path)), "--api-key", FICTIONAL_KEY],
        tmp_path,
        capsys,
    )


def test_unknown_positional_secret_is_rejected_without_echo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _assert_sanitized_parse_failure(
        [*_arguments(_paths(tmp_path)), f"unexpected-{FICTIONAL_KEY}"],
        tmp_path,
        capsys,
    )


def test_unknown_option_value_is_rejected_without_echo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _assert_sanitized_parse_failure(
        [
            *_arguments(_paths(tmp_path)),
            "--fictional-secret",
            f"value-{FICTIONAL_KEY}",
        ],
        tmp_path,
        capsys,
    )


def test_abbreviated_unsupported_option_is_rejected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _paths(tmp_path)
    _assert_sanitized_parse_failure(
        [*_arguments(paths), "--authorization", str(paths[0])],
        tmp_path,
        capsys,
    )


def test_cli_exposes_only_fixed_non_secret_options() -> None:
    parser = cli._parser()

    destinations = {action.dest for action in parser._actions}  # noqa: SLF001
    assert destinations == {
        "help",
        "authorization_json",
        "pricing_json",
        "data_controls_json",
        "execute_real_preflight",
        "confirmation",
    }
    assert {
        "authorization_json",
        "pricing_json",
        "data_controls_json",
    } == {
        action.dest
        for action in parser._actions  # noqa: SLF001
        if action.type is Path
    }
    assert parser.allow_abbrev is False


def test_public_cli_signature_has_no_dependency_injection_surface() -> None:
    parameters = inspect.signature(cli.main).parameters

    assert tuple(parameters) == ("argv",)
    assert not {
        "repository_root",
        "api_key_reader",
        "client_factory",
        "clock",
    } & set(parameters)
    assert cli._main_for_tests.__name__.startswith("_")


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt(), SystemExit(9)))
def test_keyboard_interrupt_and_system_exit_from_readiness_propagate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt: BaseException,
) -> None:
    paths = _paths(tmp_path)

    def interrupted(**kwargs: object) -> object:
        raise interrupt

    monkeypatch.setattr(
        execution,
        "validate_openai_preflight_readiness",
        interrupted,
    )

    with pytest.raises(type(interrupt)):
        cli.main(_arguments(paths))


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt(), SystemExit(9)))
def test_keyboard_interrupt_and_system_exit_from_execution_propagate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt: BaseException,
) -> None:
    paths = _paths(tmp_path)

    def interrupted(**kwargs: object) -> object:
        raise interrupt

    monkeypatch.setattr(
        execution,
        "execute_openai_synthetic_preflight",
        interrupted,
    )

    with pytest.raises(type(interrupt)):
        cli.main(
            [
                *_arguments(paths),
                "--execute-real-preflight",
                "--confirmation",
                execution.EXECUTION_CONFIRMATION,
            ]
        )
