"""TREVLIX – sichere Git-Operationen für Admin-Updater.

Kapselt subprocess-Aufrufe für Git in eine klar testbare Service-Schicht.
Alle Kommandos verwenden feste Argumentlisten (kein Shell-Parsing) und
laufen ausschließlich im TREVLIX-Repository.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("trevlix.git_ops")
_DEFAULT_VERSION = os.getenv("TREVLIX_VERSION", "1.5.2")


@dataclass(frozen=True)
class UpdateStatus:
    current_version: str
    latest_version: str
    update_available: bool
    repo: str
    branch: str
    last_check: str

    def to_socket_payload(self) -> dict[str, str | bool]:
        return {
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "current": self.current_version,  # backward compatibility
            "latest": self.latest_version,  # backward compatibility
            "update_available": self.update_available,
            "repo": self.repo,
            "branch": self.branch,
            "last_check": self.last_check,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_git(args: list[str], timeout: int = 10, check: bool = False) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    return subprocess.run(
        cmd,
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def get_update_status() -> UpdateStatus:
    repo_url_proc = _run_git(["remote", "get-url", "origin"], timeout=5)
    branch_proc = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    tag_proc = _run_git(["describe", "--tags", "--abbrev=0"], timeout=5)

    repo_url = repo_url_proc.stdout.strip() if repo_url_proc.returncode == 0 else ""
    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "main"
    current = (tag_proc.stdout.strip() if tag_proc.returncode == 0 else "") or _DEFAULT_VERSION
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return UpdateStatus(
        current_version=current,
        latest_version=current,
        update_available=False,
        repo=repo_url,
        branch=branch,
        last_check=timestamp,
    )


def apply_update() -> None:
    _run_git(["pull", "--ff-only"], timeout=30, check=True)


def rollback_update() -> bool:
    stash_proc = _run_git(["stash"], timeout=15, check=False)
    if stash_proc.returncode != 0:
        log.warning("git stash failed: %s", stash_proc.stderr.strip())
        return False
    return True
