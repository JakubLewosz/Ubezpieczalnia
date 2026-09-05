"""Manage isolated PostgreSQL/Redis development processes; never system services."""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import psycopg
from dotenv import dotenv_values
from psycopg import sql


def binary(name):
    explicit = os.environ.get("BROKER_PG_BIN")
    candidates = ([str(Path(explicit) / name)] if explicit else []) + [
        f"/opt/homebrew/opt/postgresql@17/bin/{name}",
        f"/usr/local/opt/postgresql@17/bin/{name}",
        f"/usr/lib/postgresql/17/bin/{name}",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"Brak programu {name}; zainstaluj wymagania z README.md.")


def redis_query(port, *arguments):
    try:
        return subprocess.run(
            [binary("redis-cli"), "-h", "127.0.0.1", "-p", port, "--raw", *arguments],
            capture_output=True, text=True, check=False, timeout=3,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"Port Redis {port} nie odpowiada prawidłowo; nie zmieniono instancji.") from None


def owned_redis_running(port, local):
    """Only reuse a Redis with this checkout's PID file and data directory."""
    ping = redis_query(port, "PING")
    if ping.returncode:
        return False

    def refuse_foreign():
        raise SystemExit(
            f"Konflikt portu Redis {port}: instancja nie należy do tego katalogu projektu. "
            "Nie wykonano SHUTDOWN ani zmiany jej konfiguracji."
        )

    if ping.stdout.strip() != "PONG":
        refuse_foreign()
    pid_file = local / "redis.pid"
    try:
        expected_pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        refuse_foreign()
    if expected_pid <= 0:
        refuse_foreign()
    info = redis_query(port, "INFO", "server")
    info_fields = dict(line.split(":", 1) for line in info.stdout.splitlines()
                       if ":" in line and not line.startswith("#"))
    if info.returncode or info_fields.get("process_id") != str(expected_pid):
        refuse_foreign()
    config = redis_query(port, "CONFIG", "GET", "dir", "pidfile")
    config_lines = config.stdout.splitlines()
    if config.returncode or len(config_lines) != 4:
        refuse_foreign()
    config_fields = dict(zip(config_lines[::2], config_lines[1::2], strict=True))
    if (Path(config_fields.get("dir", "")).resolve() != (local / "redis").resolve()
            or Path(config_fields.get("pidfile", "")).resolve() != pid_file.resolve()):
        refuse_foreign()
    return True


def main():
    parser = argparse.ArgumentParser(description="Prywatne, lokalne usługi DANE TESTOWE.")
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    cfg = {**dotenv_values(ROOT / ".env"), **os.environ}
    if cfg.get("DJANGO_ENV") != "development":
        parser.exit(1, "To polecenie wymaga DJANGO_ENV=development w .env.\n")
    if cfg.get("POSTGRES_HOST", "127.0.0.1") != "127.0.0.1":
        parser.exit(1, "Lokalne usługi obsługują tylko POSTGRES_HOST=127.0.0.1.\n")
    local = ROOT / ".local"
    data = local / "postgres"
    local.mkdir(mode=0o700, exist_ok=True)
    port = str(int(cfg.get("POSTGRES_PORT", "54329")))
    from urllib.parse import urlparse
    redis_url = urlparse(cfg.get("REDIS_URL", "redis://127.0.0.1:56379/0"))
    if redis_url.hostname != "127.0.0.1":
        parser.exit(1, "Lokalny Redis obsługuje tylko adres 127.0.0.1.\n")
    redis_port = str(redis_url.port or 56379)
    # Check ownership before starting/stopping either service in this checkout.
    redis_running = owned_redis_running(redis_port, local)
    if args.action == "stop":
        if (data / "postmaster.pid").exists():
            subprocess.run([binary("pg_ctl"), "-D", str(data), "-m", "fast", "stop"], check=True)
        if redis_running and owned_redis_running(redis_port, local):
            stopped = redis_query(redis_port, "SHUTDOWN")
            if stopped.returncode:
                parser.exit(1, "Nie udało się zatrzymać własnej instancji Redis.\n")
        return
    if args.action == "status":
        subprocess.run([binary("pg_ctl"), "-D", str(data), "status"], check=False)
        print("Redis: własna instancja działa." if redis_running else "Redis: zatrzymany.")
        return
    password = cfg.get("POSTGRES_PASSWORD")
    secret = cfg.get("DJANGO_SECRET_KEY")
    if not password or not secret:
        parser.exit(1, "Najpierw uruchom scripts/generate_local_config.py.\n")
    if not (data / "PG_VERSION").exists():
        subprocess.run([
            binary("initdb"), "-D", str(data), "--username=broker_bootstrap",
            "--auth-local=trust", "--auth-host=scram-sha-256", "--encoding=UTF8", "--locale=C",
        ], check=True)
    if (data / "PG_VERSION").read_text().strip() != "17":
        parser.exit(1, "Istniejący katalog ma inną wersję PostgreSQL; nie został zmieniony.\n")
    socket_dir = local / "pgsocket"
    socket_dir.mkdir(mode=0o700, exist_ok=True)
    if not (data / "postmaster.pid").exists():
        subprocess.run([
            binary("pg_ctl"), "-D", str(data), "-l", str(local / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port} -k '{socket_dir}'", "-w", "start",
        ], check=True)
    with psycopg.connect(host=str(socket_dir), port=port, user="broker_bootstrap", dbname="postgres",
                         autocommit=True) as conn:
        user = cfg.get("POSTGRES_USER", "broker")
        database = cfg.get("POSTGRES_DB", "broker_office")
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [user]).fetchone():
            # Django test runner requires CREATEDB in this isolated development cluster.
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN CREATEDB PASSWORD {}").format(
                sql.Identifier(user), sql.Literal(password)))
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", [database]).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(database), sql.Identifier(user)))
    redis_data = local / "redis"
    redis_data.mkdir(mode=0o700, exist_ok=True)
    if not redis_running:
        subprocess.run([
            binary("redis-server"), "--bind", "127.0.0.1", "--port", redis_port,
            "--protected-mode", "yes", "--daemonize", "yes", "--appendonly", "yes",
            "--dir", str(redis_data), "--pidfile", str(local / "redis.pid"),
            "--logfile", str(local / "redis.log"), "--maxmemory", "256mb",
            "--maxmemory-policy", "noeviction",
        ], check=True)
        for _ in range(20):
            time.sleep(0.1)
            if owned_redis_running(redis_port, local):
                break
        else:
            parser.exit(1, "Własna instancja Redis nie rozpoczęła pracy. Sprawdź .local/redis.log.\n")
    print(f"DANE TESTOWE: PostgreSQL 127.0.0.1:{port}, Redis 127.0.0.1:{redis_port}.")


if __name__ == "__main__":
    main()
