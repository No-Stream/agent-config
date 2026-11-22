"""Copy the shareable parts of the local Claude Code and Codex config into this repo, redacting personal details.

Only the paths in COPIED_FILES and COPIED_DIRS are copied. After copying, every file git could publish (tracked, or
untracked and not ignored) is scanned for the forbidden patterns and the script fails if any match, so a later edit to
the live config cannot leak through a re-sync unnoticed.
The paths in REPO_OWNED are edited in this repo and symlinked into the live config at the paths they map to, so the sync
never deletes or overwrites them, and it leaves alone any live path that is itself a symlink into this repo.
Names that must not appear (clients, projects, email) live in the gitignored PRIVATE_PATTERNS_FILE, one regex per line,
and private text substitutions in PRIVATE_REPLACEMENTS_FILE, one `old<TAB>new` per line, so this script does not
publish them.

Run: python3 sync.py. The local git hooks run python3 sync.py --check, which only scans the repo as it stands, and
python3 sync.py --check-commits <sha>..., which scans the message and added lines of each commit being pushed.
scripts/link-repo-owned.sh links the repo-owned paths into ~/.claude; see README.md, Installing.
"""

import argparse
import logging
import re
import shutil
import subprocess
from pathlib import Path

logger: logging.Logger = logging.getLogger(__name__)

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parent

COPIED_FILES: dict[str, str] = {
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
# Repo path to live path under ~; link-repo-owned.sh links a .claude/rules/ entry, a machine layer, only for --layer.
REPO_OWNED: dict[str, str] = {
    "instructions/core.md": ".claude/CLAUDE.md",
    "instructions/personal.md": ".claude/rules/personal.md",
    "claude/skills/write-plainly": ".claude/skills/write-plainly",
    "claude/skills/notebooks": ".claude/skills/notebooks",
    "claude/agents/prose-reviewer.md": ".claude/agents/prose-reviewer.md",
    "claude/agents/prose-fidelity-checker.md": ".claude/agents/prose-fidelity-checker.md",
    "claude/agents/prose-reader-test.md": ".claude/agents/prose-reader-test.md",
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


def git(*args: str) -> str:
    command = ["git", "-C", str(REPO_ROOT), *args]
    return subprocess.run(command, check=True, capture_output=True, encoding="utf-8", errors="replace").stdout


def matching_patterns(line: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, line, flags=re.IGNORECASE)]


def publishable_files() -> list[Path]:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return [REPO_ROOT / name for name in sorted(set(listed)) if name and (REPO_ROOT / name).is_file()]


def scan_for_leaks() -> list[str]:
    forbidden_patterns = load_forbidden_patterns()
    leaks = []
    for path in publishable_files():
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            for pattern in matching_patterns(line, forbidden_patterns):
                leaks.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: matches {pattern!r}")
    return leaks


def scan_commits(commits: list[str]) -> list[str]:
    """Leaks in each commit's message and added lines, so a leak that a later commit deleted still counts."""
    forbidden_patterns = load_forbidden_patterns()
    leaks = []
    for commit in commits:
        for line_number, line in enumerate(git("log", "-1", "--format=%B", commit).splitlines(), start=1):
            for pattern in matching_patterns(line, forbidden_patterns):
                leaks.append(f"{commit} message line {line_number}: matches {pattern!r}")
        diff = git("show", "--format=", "--unified=0", "--no-color", "--no-ext-diff", "--no-prefix", "--diff-merges=first-parent", commit)
        path, in_hunk = "", False
        for line in diff.splitlines():
            if line.startswith("diff --git "):
                in_hunk = False
            elif line.startswith("@@"):
                in_hunk = True
            elif not in_hunk and line.startswith("+++ "):
                path = line[len("+++ ") :]
            elif in_hunk and line.startswith("+"):
                for pattern in matching_patterns(line[1:], forbidden_patterns):
                    leaks.append(f"{commit} {path}: added line matches {pattern!r}")
    return leaks


def fail_on_leaks(leaks: list[str], advice: str) -> None:
    if leaks:
        raise SystemExit(f"Sensitive patterns found; {advice}:\n" + "\n".join(leaks))


def is_repo_owned(path: Path) -> bool:
    relative = path.relative_to(REPO_ROOT)
    return any(relative == Path(owned) or Path(owned) in relative.parents for owned in REPO_OWNED)


def links_into_repo(source: Path, destination: Path) -> bool:
    target = source.resolve()
    if not target.is_relative_to(REPO_ROOT):
        return False
    if target != destination:
        raise ValueError(f"{source} links to {target}, but the sync would copy it to {destination}")
    return True


def planned_copies() -> list[tuple[Path, Path]]:
    """Every (live source, repo destination) pair the sync copies with redaction, repo-owned paths excluded."""
    copies = [(HOME / source, REPO_ROOT / destination) for source, destination in COPIED_FILES.items()]
    for source_dir, destination_dir in COPIED_DIRS.items():
        for source in sorted((HOME / source_dir).rglob("*")):
            if not source.is_dir() and not IGNORED_NAMES.intersection(source.parts):
                copies.append((source, REPO_ROOT / destination_dir / source.relative_to(HOME / source_dir)))
    return [(source, destination) for source, destination in copies if not is_repo_owned(destination)]


def remove_stale_files(kept: set[Path]) -> None:
    """Delete files under the synced directories that are neither kept nor repo-owned, then the directories left empty."""
    destinations = [*COPIED_FILES.values(), *COPIED_DIRS.values()]
    for synced_dir in {Path(destination).parts[0] for destination in destinations if "/" in destination}:
        for path in sorted((REPO_ROOT / synced_dir).rglob("*"), reverse=True):
            if path in kept or is_repo_owned(path):
                continue
            if not path.is_dir():
                path.unlink()
            elif not any(path.iterdir()):
                path.rmdir()


def sync() -> None:
    copies = planned_copies()
    linked_paths = {destination for source, destination in copies if links_into_repo(source, destination)}
    written_paths = []
    for source, destination in copies:
        if destination not in linked_paths:
            copy_redacted(source, destination)
            written_paths.append(destination)

    codex_config_source = HOME / CODEX_CONFIG
    write_text(REPO_ROOT / "codex/config.toml", redact(sanitize_codex_config(codex_config_source.read_text())), codex_config_source)
    codex_rules_source = HOME / CODEX_RULES
    write_text(REPO_ROOT / "codex/rules/default.rules", redact(keep_forbidden_codex_rules(codex_rules_source.read_text())), codex_rules_source)
    written_paths += [REPO_ROOT / "codex/config.toml", REPO_ROOT / "codex/rules/default.rules"]

    remove_stale_files(set(written_paths) | linked_paths)
    fail_on_leaks(scan_for_leaks(), "fix the redaction before committing")
    logger.info("Synced %d files with no sensitive patterns found", len(written_paths))


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy the shareable live config into this repo and scan it for leaks.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="only scan the repo for sensitive patterns; exit 1 on any match")
    mode.add_argument(
        "--check-commits", nargs="+", metavar="SHA", help="scan each commit's message and added lines; exit 1 on any match"
    )
    mode.add_argument(
        "--list-repo-owned", action="store_true", help="print each repo-owned path and its live path under ~, tab-separated"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.check:
        fail_on_leaks(scan_for_leaks(), "remove them before committing")
        logger.info("No sensitive patterns found")
    elif args.check_commits:
        fail_on_leaks(scan_commits(args.check_commits), "rewrite these commits before pushing")
        logger.info("No sensitive patterns found in %d commits", len(args.check_commits))
    elif args.list_repo_owned:
        print("\n".join(f"{repo_path}\t{live_path}" for repo_path, live_path in REPO_OWNED.items()))
    else:
        sync()


if __name__ == "__main__":
    main()
