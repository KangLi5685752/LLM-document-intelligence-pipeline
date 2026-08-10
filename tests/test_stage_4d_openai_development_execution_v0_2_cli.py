"""Offline default-deny CLI tests for the Stage 4D v0.2 development transaction."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from document_intelligence.llm_extraction import (
    openai_development_execution_v0_2 as execution,
)
from document_intelligence.llm_extraction import (
    openai_development_execution_v0_2_cli as cli,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _arguments(tmp_path: Path) -> list[str]:
    return [
        "--authorization-json",
        str(tmp_path / "fictional-authorization.json"),
        "--pricing-json",
        str(tmp_path / "fictional-pricing.json"),
        "--data-controls-json",
        str(tmp_path / "fictional-data-controls.json"),
    ]


def _forbidden(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("default readiness crossed a provider boundary")


def test_cli_defaults_to_no_call_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    def readiness(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            plan=SimpleNamespace(
                execution_id=execution.EXECUTION_ID,
                execution_plan_sha256=execution.EXPECTED_EXECUTION_PLAN_SHA256,
            ),
            existing_execution_record=None,
        )

    monkeypatch.setattr(
        execution, "_validate_openai_development_execution_readiness_v0_2", readiness
    )
    result = cli._main_for_tests(
        _arguments(tmp_path),
        repository_root=tmp_path,
        api_key_reader=_forbidden,
        client_factory=_forbidden,
        provider_observation=_forbidden,
        local_validator=_forbidden,
    )

    assert result == 0
    assert calls == 1
    assert capsys.readouterr().out == (
        '{"execution_id":"openai-gpt-5.4-mini-five-source-development-'
        'execution-v0.2","execution_plan_sha256":"25588680A1362AC0192A378CD54288'
        'AA2DF5584F4C6108E3467BA06DA68AACE9","mode":"readiness",'
        '"status":"ready"}\n'
    )


@pytest.mark.parametrize("confirmation", [None, "wrong confirmation"])
def test_cli_real_mode_requires_exact_confirmation_before_all_side_effects(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    confirmation: str | None,
) -> None:
    arguments = [*_arguments(tmp_path), "--execute-real-development"]
    if confirmation is not None:
        arguments.extend(("--confirmation", confirmation))

    result = cli._main_for_tests(
        arguments,
        repository_root=tmp_path,
        api_key_reader=_forbidden,
        client_factory=_forbidden,
        reconstructor=_forbidden,
        provider_observation=_forbidden,
        local_validator=_forbidden,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert '"error_code":"development_execution_gate_invalid"' in captured.err
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize(
    "forbidden_option",
    [
        "--repository-root",
        "--output-root",
        "--cache-root",
        "--cache-bypass",
        "--authorization-create",
        "--retry",
    ],
)
def test_cli_has_no_path_cache_authorization_or_retry_bypass(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    forbidden_option: str,
) -> None:
    with pytest.raises(SystemExit) as captured:
        cli._main_for_tests(
            [*_arguments(tmp_path), forbidden_option, "fictional-value"],
            repository_root=tmp_path,
        )

    assert captured.value.code == 2
    streams = capsys.readouterr()
    assert streams.out == ""
    assert streams.err == (
        '{"error_code":"invalid_cli_arguments",'
        '"message":"Invalid command-line arguments"}\n'
    )


def test_public_entrypoints_expose_no_dependency_injection() -> None:
    assert tuple(inspect.signature(cli.main).parameters) == ("argv",)
    assert tuple(inspect.signature(execution.execute_openai_development_v0_2).parameters) == (
        "authorization_path",
        "pricing_path",
        "data_controls_path",
        "execute_real_development",
        "confirmation",
    )


def test_pyproject_exposes_default_deny_development_execution_cli() -> None:
    pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    scripts = pyproject.split("[project.scripts]", maxsplit=1)[1].split(
        "\n[", maxsplit=1
    )[0]
    expected = (
        "run-openai-development-execution-v0-2 = "
        '"document_intelligence.llm_extraction.'
        'openai_development_execution_v0_2_cli:main"'
    )

    assert scripts.count(expected) == 1
