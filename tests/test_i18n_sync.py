"""i18n key sync test.

Prevents the drift documented in ``tasks/lessons.md`` (Lektion 17):
every ``data-i18n`` / ``data-i18n-html`` key referenced in a Jinja
template must exist in either ``static/js/trevlix_translations.js``
(dashboard) or ``static/js/page_i18n.js`` (public pages) and must
carry translations for all five supported languages (de, en, es, ru, pt).

Also validates that every key added to a translations file is picked
up by every language. Missing languages are treated as missing keys.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
TRANSLATIONS_FILES = (
    REPO_ROOT / "static" / "js" / "trevlix_translations.js",
    REPO_ROOT / "static" / "js" / "page_i18n.js",
)
REQUIRED_LANGS = frozenset({"de", "en", "es", "ru", "pt"})

# Templates that ship their own inline i18n dict (no dependency on
# trevlix_translations.js / page_i18n.js). Auth-Seiten tragen den Übersetzungs-
# Kontext aus Sicherheitsgründen (minimaler externer JS-Surface) selbst im
# Template. Die Drift-Prüfung ist hier daher nicht anwendbar.
_SELF_TRANSLATED = frozenset({"auth.html", "auth_admin.html"})

# Matches `ident: { ... }` entries whose body contains no nested braces.
# Keeps the parser cheap and safe for the flat QT/PT dicts.
_ENTRY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{([^{}]*)\}")
_LANG_RE = re.compile(r"\b(de|en|es|ru|pt)\s*:")

# Picks up both data-i18n="..." and data-i18n-html="..."
_I18N_ATTR_RE = re.compile(r'data-i18n(?:-html)?\s*=\s*"([^"]+)"')


def _parse_translations(path: Path) -> set[str]:
    """Return the set of keys that have entries for all five languages."""
    text = path.read_text(encoding="utf-8")
    keys: set[str] = set()
    for match in _ENTRY_RE.finditer(text):
        key, body = match.group(1), match.group(2)
        langs = set(_LANG_RE.findall(body))
        if REQUIRED_LANGS.issubset(langs):
            keys.add(key)
    return keys


def _extract_template_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(_I18N_ATTR_RE.findall(text))


def test_all_template_i18n_keys_have_translations() -> None:
    """Every data-i18n key in templates/ must be fully translated."""
    available: set[str] = set()
    for js_file in TRANSLATIONS_FILES:
        assert js_file.exists(), f"Missing translations file: {js_file}"
        available |= _parse_translations(js_file)

    missing: dict[str, list[str]] = {}
    for tpl in sorted(TEMPLATES_DIR.rglob("*.html")):
        if tpl.name in _SELF_TRANSLATED:
            continue
        orphans = _extract_template_keys(tpl) - available
        if orphans:
            missing[tpl.relative_to(REPO_ROOT).as_posix()] = sorted(orphans)

    if missing:
        report = "\n".join(
            f"  {fname}: {', '.join(keys)}" for fname, keys in sorted(missing.items())
        )
        raise AssertionError(
            "data-i18n keys missing from trevlix_translations.js / page_i18n.js "
            "(or lacking one of de/en/es/ru/pt):\n" + report
        )


def test_translations_files_contain_required_keys() -> None:
    """Sanity check: parser is finding keys — not silently passing."""
    qt = _parse_translations(TRANSLATIONS_FILES[0])
    pt = _parse_translations(TRANSLATIONS_FILES[1])
    # Pick a couple of keys we know should exist.
    assert "nav_home" in qt or "nav_home" in pt
    assert "footer_product" in pt
    assert len(qt) > 100, f"QT parser returned only {len(qt)} keys"
    assert len(pt) > 50, f"PT parser returned only {len(pt)} keys"
