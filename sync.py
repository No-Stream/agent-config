"""Copy the shareable parts of the local Claude Code and Codex config into this repo, redacting personal details.

Only the paths in COPIED_FILES and COPIED_DIRS are copied. After copying, every file is scanned for FORBIDDEN_PATTERNS
and the script fails if any match, so a later edit to the live config cannot leak through a re-sync unnoticed.
Names that must not appear (clients, projects, email) live in the gitignored PRIVATE_PATTERNS_FILE, one regex per line,
and private text substitutions in PRIVATE_REPLACEMENTS_FILE, one `old<TAB>new` per line, so this script does not
publish them.

Run: python3 sync.py
"""

import logging
import re
import shutil
from pathlib import Path

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parent

COPIED_FILES: dict[str, str] = {
    "AGENTS.md": "AGENTS.md",
    ".claude/settings.json": "claude/settings.json",
    ".claude/statusline-command.sh": "claude/statusline-command.sh",
    ".claude/hooks/guard-bash.sh": "claude/hooks/guard-bash.sh",
    ".codex/hooks/guard_shell.py": "codex/hooks/guard_shell.py",
    ".codex/hooks/guard_shell_cases.tsv": "codex/hooks/guard_shell_cases.tsv",
    ".codex/hooks/test_guard_shell.sh": "codex/hooks/test_guard_shell.sh",
}
COPIED_DIRS: dict[str, str] = {
    ".claude/agents": "claude/agents",
    ".claude/skills/paper-drafting": "claude/skills/paper-drafting",
    ".claude/skills/review": "claude/skills/review",
    ".claude/skills/visualization": "claude/skills/visualization",
}
CODEX_CONFIG = ".codex/config.toml"
CODEX_RULES = ".codex/rules/default.rules"

# Per-project trust entries, a machine-specific hook hash, and UI migration state.
CODEX_DROPPED_TABLE_PREFIXES = ("[projects.", "[hooks.state.", "[notice", "[tui.model_availability_nux]")

PRIVATE_PATTERNS_FILE = REPO_ROOT / ".private" / "forbidden_patterns.txt"
PRIVATE_REPLACEMENTS_FILE = REPO_ROOT / ".private" / "replacements.tsv"

TEXT_REPLACEMENTS: list[tuple[str, str]] = [
    (str(HOME), "~"),
    (f"--user-name {HOME.name}", "--user-name example-user"),
]

GENERIC_FORBIDDEN_PATTERNS: list[str] = [
    re.escape(str(HOME)),
    r"\bgh[opsu]_[A-Za-z0-9]{20,}",
    r"\bsk-[A-Za-z0-9_-]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"BEGIN [A-Z ]*PRIVATE KEY",
]
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".git", ".private"}


def load_private_replacements() -> list[tuple[str, str]]:
    rows = [line.split("\t") for line in PRIVATE_REPLACEMENTS_FILE.read_text().splitlines() if line.strip()]
    malformed_rows = [row for row in rows if len(row) != 2]
    if malformed_rows:
        raise ValueError(f"{PRIVATE_REPLACEMENTS_FILE} rows must be old<TAB>new, got {malformed_rows}")
    return [(old, new) for old, new in rows]


def redact(text: str) -> str:
    for old, new in TEXT_REPLACEMENTS + load_private_replacements():
        text = text.replace(old, new)
    return text


def sanitize_codex_config(text: str) -> str:
    kept_lines = []
    keep_current_table = True
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            keep_current_table = not stripped.startswith(CODEX_DROPPED_TABLE_PREFIXES)
        if not keep_current_table:
            continue
        if stripped.startswith("writable_roots"):
            roots = re.findall(r'"([^"]+)"', stripped)
            shared_roots = ", ".join(f'"{root}"' for root in roots if "/workspace/" not in root)
            line = f"writable_roots = [{shared_roots}]"
        kept_lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip() + "\n"


def keep_forbidden_codex_rules(text: str) -> str:
    """Keep comments and the hand-written `forbidden` rules; drop the auto-saved per-command approvals."""
    kept_chunks = []
    current_block: list[str] = []
    for line in text.splitlines():
        if current_block:
            current_block.append(line)
            if line.strip() == ")":
                block_text = "\n".join(current_block)
                if 'decision="forbidden"' in block_text:
                    kept_chunks.append(block_text)
                current_block = []
        elif line.startswith("prefix_rule(") and line.rstrip().endswith(")"):
            continue
        elif line.startswith("prefix_rule("):
            current_block = [line]
        elif line.startswith("#"):
            kept_chunks.append(line)
    if current_block:
        raise ValueError(f"Unterminated prefix_rule block in {CODEX_RULES}: {current_block[0]}")
    return "\n\n".join(kept_chunks) + "\n"


def write_text(destination: Path, text: str, mode_source: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    shutil.copymode(mode_source, destination)


def copy_redacted(source: Path, destination: Path) -> None:
    write_text(destination, redact(source.read_text()), source)


def load_forbidden_patterns() -> list[str]:
    private_patterns = [line for line in PRIVATE_PATTERNS_FILE.read_text().splitlines() if line.strip()]
    if not private_patterns:
        raise ValueError(f"{PRIVATE_PATTERNS_FILE} is empty; it must list the private names to check for")
    return GENERIC_FORBIDDEN_PATTERNS + private_patterns


def scan_for_leaks() -> list[str]:
    forbidden_patterns = load_forbidden_patterns()
    repo_files = [path for path in REPO_ROOT.rglob("*") if path.is_file() and not IGNORED_NAMES.intersection(path.parts)]
    leaks = []
    for path in repo_files:
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            for pattern in forbidden_patterns:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    leaks.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: matches {pattern!r}")
    return leaks


def main() -> None:
    for destination_dir in {Path(destination).parts[0] for destination in [*COPIED_FILES.values(), *COPIED_DIRS.values()]}:
        shutil.rmtree(REPO_ROOT / destination_dir, ignore_errors=True)
    (REPO_ROOT / "AGENTS.md").unlink(missing_ok=True)

    written_paths = []
    for source, destination in COPIED_FILES.items():
        copy_redacted(HOME / source, REPO_ROOT / destination)
        written_paths.append(REPO_ROOT / destination)
    for source_dir, destination_dir in COPIED_DIRS.items():
        for source in sorted((HOME / source_dir).rglob("*")):
            if source.is_dir() or IGNORED_NAMES.intersection(source.parts):
                continue
            destination = REPO_ROOT / destination_dir / source.relative_to(HOME / source_dir)
            copy_redacted(source, destination)
            written_paths.append(destination)

    codex_config_source = HOME / CODEX_CONFIG
    write_text(REPO_ROOT / "codex/config.toml", redact(sanitize_codex_config(codex_config_source.read_text())), codex_config_source)
    codex_rules_source = HOME / CODEX_RULES
    write_text(REPO_ROOT / "codex/rules/default.rules", redact(keep_forbidden_codex_rules(codex_rules_source.read_text())), codex_rules_source)
    written_paths += [REPO_ROOT / "codex/config.toml", REPO_ROOT / "codex/rules/default.rules"]

    leaks = scan_for_leaks()
    if leaks:
        raise SystemExit("Sensitive patterns found; fix the redaction before committing:\n" + "\n".join(leaks))
    logger.info("Synced %d files with no sensitive patterns found", len(written_paths))


if __name__ == "__main__":
    main()
