#!/usr/bin/env python3
"""Validate that websocket translation keys exist for all UI languages.

Checks:
1) Every `ws_*` key emitted in `server.py` exists in `static/js/trevlix_translations.js`.
2) Every existing `ws_*` entry in translations contains all required languages.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_LANGS = {"de", "en", "es", "ru", "pt"}


def _load(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _server_ws_keys(server_text: str) -> set[str]:
    return set(re.findall(r'"key"\s*:\s*"(ws_[a-z0-9_]+)"', server_text))


def _translation_ws_entries(translations_text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    pattern = re.compile(r"(ws_[a-z0-9_]+)\s*:\s*\{([^{}]*)\}", re.MULTILINE)
    for key, body in pattern.findall(translations_text):
        entries[key] = body
    return entries


def _missing_langs(entry_body: str) -> set[str]:
    found = set(re.findall(r"\b(de|en|es|ru|pt)\s*:", entry_body))
    return REQUIRED_LANGS - found


def main() -> int:
    server_text = _load("server.py")
    trans_text = _load("static/js/trevlix_translations.js")

    ws_server = _server_ws_keys(server_text)
    ws_trans = _translation_ws_entries(trans_text)

    missing_keys = sorted(k for k in ws_server if k not in ws_trans)

    missing_lang_map: dict[str, set[str]] = {}
    for key, body in ws_trans.items():
        miss = _missing_langs(body)
        if miss:
            missing_lang_map[key] = miss

    if not missing_keys and not missing_lang_map:
        print("OK: websocket i18n keys are complete.")
        return 0

    if missing_keys:
        print("Missing ws_* keys in translations:")
        for key in missing_keys:
            print(f"  - {key}")

    if missing_lang_map:
        print("Translation entries missing languages:")
        for key in sorted(missing_lang_map):
            miss = ", ".join(sorted(missing_lang_map[key]))
            print(f"  - {key}: {miss}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
