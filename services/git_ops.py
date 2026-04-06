"""TREVLIX – sichere Git-Operationen für Admin-Updater.

Kapselt subprocess-Aufrufe für Git in eine klar testbare Service-Schicht.
Alle Kommandos verwenden feste Argumentlisten (kein Shell-Parsing) und
laufen ausschließlich im TREVLIX-Repository.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from services.utils import BOT_VERSION

log = logging.getLogger("trevlix.git_ops")
_DEFAULT_VERSION = os.getenv("TREVLIX_VERSION", BOT_VERSION)
_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class GitOperationError(RuntimeError):
    """Kontrollierter Fehler für Git-Operationen mit user-safe Message."""

    def __init__(self, user_message: str, *, detail: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


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


def _run_git(
    args: list[str], timeout: int = 10, check: bool = False
) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    try:
        return subprocess.run(
            cmd,
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as e:
        raise GitOperationError("Git-Operation hat das Timeout überschritten", detail=str(e)) from e
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or str(e)).strip()
        raise GitOperationError("Git-Operation fehlgeschlagen", detail=detail) from e
    except OSError as e:
        raise GitOperationError("Git ist nicht verfügbar", detail=str(e)) from e


def _normalize_version(raw: str | None) -> str:
    """Normalize git/python versions to plain x.y.z."""
    value = (raw or "").strip()
    if value.startswith("v"):
        value = value[1:]
    return value


def _semver_key(version: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(_normalize_version(version))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _pick_latest_version(candidates: list[str]) -> str:
    latest = ""
    latest_key: tuple[int, int, int] | None = None
    for cand in candidates:
        v = _normalize_version(cand)
        if not v:
            continue
        key = _semver_key(v)
        if key is None:
            continue
        if latest_key is None or key > latest_key:
            latest = v
            latest_key = key
    return latest


def _read_version_md() -> str:
    version_file = _repo_root() / "VERSION.md"
    try:
        text = version_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return _normalize_version(line)
    return ""


def _git_latest_local_tag() -> str:
    tag_proc = _run_git(["describe", "--tags", "--abbrev=0"], timeout=5)
    if tag_proc.returncode != 0:
        return ""
    return _normalize_version(tag_proc.stdout.strip())


def _git_latest_remote_tag() -> str:
    ls_proc = _run_git(["ls-remote", "--tags", "--refs", "origin"], timeout=10)
    if ls_proc.returncode != 0:
        return ""

    tags: list[str] = []
    for line in ls_proc.stdout.splitlines():
        parts = line.strip().split("\t", 1)
        if len(parts) != 2:
            continue
        ref = parts[1]
        if not ref.startswith("refs/tags/"):
            continue
        tag = ref.rsplit("/", 1)[-1]
        tags.append(_normalize_version(tag))
    return _pick_latest_version(tags)


def get_update_status() -> UpdateStatus:
    repo_url_proc = _run_git(["remote", "get-url", "origin"], timeout=5)
    branch_proc = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], timeout=5)

    repo_url = repo_url_proc.stdout.strip() if repo_url_proc.returncode == 0 else ""
    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "main"
    current = _pick_latest_version([_git_latest_local_tag(), _read_version_md(), BOT_VERSION, _DEFAULT_VERSION])
    latest = _pick_latest_version([_git_latest_remote_tag(), current, BOT_VERSION, _DEFAULT_VERSION]) or current
    update_available = latest != current
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return UpdateStatus(
        current_version=current,
        latest_version=latest,
        update_available=update_available,
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
