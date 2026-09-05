"""Run the four application processes against existing local services."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    from dotenv import dotenv_values

    env = {**{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}, **os.environ}
    if env.get("DJANGO_ENV") != "development":
        raise SystemExit("Uruchamianie lokalne wymaga DJANGO_ENV=development.")
    concurrency = str(max(1, int(env.get("OCR_CONCURRENCY", "1"))))
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Brak npm; zainstaluj Node.js 22 LTS.")
    commands = [
        (ROOT / "backend", [sys.executable, "manage.py", "runserver", "127.0.0.1:8000", "--noreload"]),
        (ROOT / "backend", [sys.executable, "-m", "celery", "-A", "config", "worker", "--loglevel=WARNING",
                            f"--concurrency={concurrency}", "--prefetch-multiplier=1", "--max-tasks-per-child=20"]),
        (ROOT / "backend", [sys.executable, "-m", "celery", "-A", "config", "beat", "--loglevel=WARNING",
                            f"--schedule={ROOT / '.local' / 'celerybeat-schedule'}"]),
        (ROOT / "frontend", [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"]),
    ]
    processes = []
    def stop_processes(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_processes)
    try:
        for cwd, command in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=os.name != "nt"))
        print("DANE TESTOWE: http://127.0.0.1:5173 - Ctrl+C kończy procesy aplikacji.", flush=True)
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise SystemExit(f"Proces aplikacji zakończył pracę z kodem {process.returncode}.")
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == "nt":
                    process.terminate()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()


if __name__ == "__main__":
    main()
