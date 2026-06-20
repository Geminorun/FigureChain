from types import SimpleNamespace

from pytest import MonkeyPatch
from typer.testing import CliRunner

from figure_data import cli as cli_module
from figure_data.cli import app

runner = CliRunner()


def test_run_api_help_is_registered() -> None:
    result = runner.invoke(app, ["run-api", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--reload" in result.stdout


def test_run_api_starts_fastapi_with_defaults(monkeypatch: MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(app_path: str, **kwargs: object) -> None:
        calls.append({"app_path": app_path, **kwargs})

    monkeypatch.setattr(cli_module, "uvicorn", SimpleNamespace(run=fake_run), raising=False)

    result = runner.invoke(app, ["run-api"])

    assert result.exit_code == 0
    assert calls == [
        {
            "app_path": "figure_chain.app:create_app",
            "factory": True,
            "host": "127.0.0.1",
            "port": 8000,
            "reload": False,
        }
    ]


def test_run_api_accepts_host_port_and_reload(monkeypatch: MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(app_path: str, **kwargs: object) -> None:
        calls.append({"app_path": app_path, **kwargs})

    monkeypatch.setattr(cli_module, "uvicorn", SimpleNamespace(run=fake_run), raising=False)

    result = runner.invoke(
        app,
        ["run-api", "--host", "0.0.0.0", "--port", "9000", "--reload"],
    )

    assert result.exit_code == 0
    assert calls == [
        {
            "app_path": "figure_chain.app:create_app",
            "factory": True,
            "host": "0.0.0.0",
            "port": 9000,
            "reload": True,
        }
    ]

