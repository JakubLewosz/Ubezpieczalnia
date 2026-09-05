"""Allowlist test metadata only; never publish raw logs, sessions or HTTP traces."""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    summary = {"data": "DANE TESTOWE", "commit": os.environ.get("GITHUB_SHA", "local")}
    pytest_path = ROOT / ".local/pytest-results.xml"
    if pytest_path.exists():
        suites = ET.parse(pytest_path).getroot()
        summary["pytest"] = [
            {key: suite.attrib.get(key) for key in ("name", "tests", "failures", "errors", "skipped", "time")}
            for suite in suites.iter("testsuite")
        ]
        summary["pytest_failed_tests"] = [
            {"class": case.attrib.get("classname"), "name": case.attrib.get("name")}
            for case in suites.iter("testcase")
            if case.find("failure") is not None or case.find("error") is not None
        ]
    playwright_path = ROOT / ".local/playwright-results.json"
    if playwright_path.exists():
        report = json.loads(playwright_path.read_text())
        summary["playwright"] = {
            key: report.get("stats", {}).get(key)
            for key in ("startTime", "duration", "expected", "unexpected", "flaky", "skipped")
        }
        failures = []

        def collect(suites):
            for suite in suites:
                for spec in suite.get("specs", []):
                    if not spec.get("ok", True):
                        failures.append({key: spec.get(key) for key in ("title", "file", "line", "column")})
                collect(suite.get("suites", []))

        collect(report.get("suites", []))
        summary["playwright_failed_tests"] = failures
    output = ROOT / ".local/ci-diagnostics"
    output.mkdir(parents=True, exist_ok=True)
    (output / "test-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print("Zapisano wyłącznie podsumowanie i identyfikatory testów; bez treści błędów, logów i sesji.")


if __name__ == "__main__":
    main()
