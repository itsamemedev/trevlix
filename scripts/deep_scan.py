#!/usr/bin/env python3
"""Generate a reproducible deep-scan report for Trevlix."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "tasks" / "deepscan_report.md"

COUNT_SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".toml", ".yml", ".yaml"}
TOP_N = 10
SECURITY_PATTERNS = {
    "eval(...)": re.compile(r"\beval\s*\("),
    "exec(...)": re.compile(r"\bexec\s*\("),
    "pickle.loads(...)": re.compile(r"\bpickle\.loads\s*\("),
    "yaml.load(...)": re.compile(r"\byaml\.load\s*\("),
    "subprocess.run(..., shell=True)": re.compile(r"\bsubprocess\.run\s*\([^)]*shell\s*=\s*True"),
}


@dataclass
class CmdResult:
    cmd: str
    code: int
    output: str


def run_cmd(cmd: str) -> CmdResult:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        shell=True,
        text=True,
        capture_output=True,
    )
    output = (proc.stdout + proc.stderr).strip()
    return CmdResult(cmd=cmd, code=proc.returncode, output=output)


def iter_count_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or ".venv" in path.parts or "venv" in path.parts:
            continue
        if path.suffix.lower() in COUNT_SUFFIXES:
            files.append(path)
    return files


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        return sum(1 for _ in fh)


def find_subprocess_locations() -> list[str]:
    target = ROOT / "server.py"
    lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    for i, line in enumerate(lines, start=1):
        if "subprocess.run(" in line:
            out.append(f"server.py:{i}")
    return out


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        if ".git" in path.parts or ".venv" in path.parts or "venv" in path.parts:
            continue
        files.append(path)
    return files


def find_security_hits() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {name: [] for name in SECURITY_PATTERNS}
    for path in iter_python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == "scripts/deep_scan.py":
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, start=1):
            if line.lstrip().startswith("#"):
                continue
            for name, pattern in SECURITY_PATTERNS.items():
                if pattern.search(line):
                    hits[name].append(f"{rel}:{i}")
    return hits


def route_metrics() -> tuple[int, int]:
    content = (ROOT / "server.py").read_text(encoding="utf-8", errors="ignore")
    socket_count = len(re.findall(r"@socketio\.on\(", content))
    route_count = len(re.findall(r"@app\.(?:route|get|post|put|delete|patch)\(", content))
    return socket_count, route_count


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")  # noqa: UP017

    commands = [
        "python --version && pip --version && pytest --version",
        "ruff check .",
        "python -m compileall -q services routes ai_engine.py server.py trevlix_i18n.py validate_env.py",
        "python -m pip check",
        "pytest -q",
    ]
    cmd_results = [run_cmd(cmd) for cmd in commands]

    count_files = iter_count_files()
    sized = [(line_count(p), p.relative_to(ROOT).as_posix()) for p in count_files]
    sized.sort(reverse=True)

    total_files = len(sized)
    total_lines = sum(lines for lines, _ in sized)
    top_files = sized[:TOP_N]

    socket_count, route_count = route_metrics()
    subprocess_locations = find_subprocess_locations()
    security_hits = find_security_hits()

    def status(code: int) -> str:
        return "PASS" if code == 0 else "FAIL"

    report = [
        "# Trevlix Deep Scan Report",
        "",
        f"Generated: {now}",
        "Scope: Whole-project static scan + lightweight runtime checks",
        "",
        "## Executive Summary",
        "",
        f"- Scanned **{total_files} files** with **{total_lines:,} total lines** (selected source/docs/config extensions).",
        f"- Largest hotspot remains `server.py` with **{next((n for n, p in sized if p == 'server.py'), 0):,} lines**.",
        f"- Server surface area: **{socket_count}** Socket.IO handlers and **{route_count}** app routes in `server.py`.",
        "- Security quick-check now includes project-wide pattern scanning for `eval`, `exec`, `pickle.loads`, `yaml.load`, and `subprocess.run(..., shell=True)`.",
        "",
        "## Command Results",
        "",
        "| Command | Status | Exit |",
        "|---|---|---|",
    ]

    for result in cmd_results:
        report.append(f"| `{result.cmd}` | {status(result.code)} | {result.code} |")

    report.extend(
        [
            "",
            "### Command Output (abridged)",
            "",
        ]
    )

    for result in cmd_results:
        output = result.output[:2000] if result.output else "(no output)"
        report.extend(
            [
                f"#### `{result.cmd}`",
                "```text",
                output,
                "```",
                "",
            ]
        )

    report.extend(
        [
            "## Size Hotspots (Top 10)",
            "",
            "| Lines | File |",
            "|---:|---|",
        ]
    )

    for lines, file_path in top_files:
        report.append(f"| {lines:,} | `{file_path}` |")

    report.extend(
        [
            "",
            "## Security Notes",
            "",
            "High-risk primitive scan (project-wide):",
            "",
        ]
    )

    for name, locations in security_hits.items():
        report.append(f"- `{name}`: **{len(locations)}** hit(s)")
        for loc in locations[:10]:
            report.append(f"  - `{loc}`")
        if len(locations) > 10:
            report.append(f"  - `... (+{len(locations) - 10} more)`")

    report.extend(
        [
            "",
            "`subprocess.run` locations in `server.py`:",
            "",
        ]
    )

    for loc in subprocess_locations:
        report.append(f"- `{loc}`")

    if not subprocess_locations:
        report.append("- (none)")

    report.extend(
        [
            "",
            "## Production-Readiness Next Steps",
            "",
            "1. Run scan and tests in a Python 3.11 runtime to match project metadata.",
            "2. Ensure dependencies are installed before `pytest` to avoid false-negative CI/local conclusions.",
            "3. Continue decomposing `server.py` into bounded modules (routes, websocket handlers, updater/admin ops).",
            "4. Add stricter audit logs and policy checks around admin-triggered git updater flows.",
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote deep-scan report: {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
