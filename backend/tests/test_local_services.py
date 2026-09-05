import importlib.util
from pathlib import Path
from subprocess import CompletedProcess

import pytest


@pytest.fixture
def service_module():
    path = Path(__file__).resolve().parents[2] / "scripts/local_services.py"
    spec = importlib.util.spec_from_file_location("broker_local_services_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mismatch", ["missing_pid", "process_id", "data_directory", "pidfile_path"])
def test_stop_refuses_foreign_redis_before_any_service_mutation(service_module, monkeypatch, tmp_path, mismatch):
    local = tmp_path / ".local"
    (local / "postgres").mkdir(parents=True)
    (local / "postgres/postmaster.pid").write_text("222\n")
    if mismatch != "missing_pid":
        (local / "redis.pid").write_text("12345\n")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert command[0] == "redis-cli", "Nie wolno zatrzymać PostgreSQL przed wykryciem obcego Redis."
        if command[-1] == "PING":
            output = "PONG\n"
        elif command[-2:] == ["INFO", "server"]:
            output = "# Server\r\nprocess_id:" + ("99999" if mismatch == "process_id" else "12345") + "\r\n"
        elif command[-4:] == ["CONFIG", "GET", "dir", "pidfile"]:
            directory = tmp_path / "foreign" if mismatch == "data_directory" else local / "redis"
            pidfile = tmp_path / "foreign.pid" if mismatch == "pidfile_path" else local / "redis.pid"
            output = f"dir\n{directory}\npidfile\n{pidfile}\n"
        else:
            pytest.fail("Niedozwolona komenda; test nie może wykonać SHUTDOWN.")
        return CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(service_module, "ROOT", tmp_path)
    monkeypatch.setattr(service_module, "binary", lambda name: name)
    monkeypatch.setattr(service_module.subprocess, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["local_services.py", "stop"])
    monkeypatch.setenv("DJANGO_ENV", "development")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:56379/0")
    with pytest.raises(SystemExit, match="nie należy do tego katalogu"):
        service_module.main()
    assert calls and not any("SHUTDOWN" in command for command in calls)


def test_redis_ownership_requires_matching_pid_and_both_paths(service_module, monkeypatch, tmp_path):
    (tmp_path / "redis.pid").write_text("12345\n")
    outputs = iter(["PONG\n", "# Server\r\nprocess_id:12345\r\n",
                    f"pidfile\n{tmp_path / 'redis.pid'}\ndir\n{tmp_path / 'redis'}\n"])
    monkeypatch.setattr(service_module, "binary", lambda name: name)
    monkeypatch.setattr(service_module.subprocess, "run", lambda command, **kwargs:
                        CompletedProcess(command, 0, stdout=next(outputs), stderr=""))
    assert service_module.owned_redis_running("56379", tmp_path)
