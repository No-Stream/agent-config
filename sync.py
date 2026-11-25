"""Copy the shareable parts of the local Claude Code and Codex config into this repo, redacting personal details.

Only the paths in COPIED_FILES and COPIED_DIRS are copied. After copying, every file git could publish (tracked, or
untracked and not ignored) is scanned for the leak patterns and the script fails if any match, so a later edit to the
live config cannot leak through a re-sync unnoticed. The leak patterns are the generic classes below (secrets,
account numbers, ARNs, buckets, internal hosts and URLs, emails, home paths, IP addresses) and the private names.
Instruction and skill text (EVERGREEN_PATHS) states only the current rule, so the scan of the tree also fails on its
dates, history wording, ticket IDs and commit hashes.
The paths in REPO_OWNED are edited in this repo and symlinked into the live config at the paths they map to, so the sync
never deletes or overwrites them, and it leaves alone any live path that is itself a symlink into this repo.
Names that must not appear (clients, projects, email) live in the gitignored PRIVATE_PATTERNS_FILE, one regex per line,
private text substitutions in PRIVATE_REPLACEMENTS_FILE, one `old<TAB>new` per line, and exceptions to the scan in
PRIVATE_ALLOWED_MATCHES_FILE, one `path<TAB>matched text<TAB>reason` per line, so this script does not publish them.

Run: python3 sync.py. The local git hooks run python3 sync.py --check, which only scans the repo as it stands, and
python3 sync.py --check-commits <sha>..., which scans the identities, message and added lines of each commit being
pushed. python3 sync.py --check-history scans every commit on any branch, remote-tracking branch or tag the same way.
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
CODEX_DROPPED_TABLE_PREFIXES = (
    "[projects.",
    "[hooks.state.",
    "[notice",
    "[tui.model_availability_nux]",
)

PRIVATE_PATTERNS_FILE = REPO_ROOT / ".private" / "forbidden_patterns.txt"
PRIVATE_REPLACEMENTS_FILE = REPO_ROOT / ".private" / "replacements.tsv"
PRIVATE_ALLOWED_MATCHES_FILE = REPO_ROOT / ".private" / "allowed_matches.tsv"

TEXT_REPLACEMENTS: list[tuple[str, str]] = [
    (str(HOME), "~"),
    (f"--user-name {HOME.name}", "--user-name example-user"),
]

PUBLIC_EMAIL = "15351234+No-Stream@users.noreply.github.com"
# AWS's documented example accounts, and the all-zero account that tests use.
EXAMPLE_AWS_ACCOUNTS = ("000000000000", "123456789012", "111122223333", "444455556666")
_EXAMPLE_ACCOUNT = "|".join(EXAMPLE_AWS_ACCOUNTS)
_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_WEEKDAY = r"(?:Mon|Tues?|Wed(?:nes)?|Thu(?:rs)?|Fri|Sat(?:ur)?|Sun)(?:day)?"

# Reported without the matched text, so a found secret is not echoed into a terminal or log.
SECRET_PATTERNS: dict[str, str] = {
    "GitHub token": r"\bgh[opsu]_[A-Za-z0-9]{20,}",
    "API key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "AWS access key or principal ID": (
        r"(?-i:\b(?:AKIA|ASIA|ABIA|ACCA|AIDA|AROA|AGPA|AIPA|ANPA|ANVA|APKA|ASCA)[0-9A-Z]{16}\b)"
    ),
    "AWS secret or session token": (
        r"\baws_(?:secret_access_key|session_token)\s*[=:]\s*[\"']?[A-Za-z0-9/+=]{16,}"
        r"|(?-i:\b(?:IQoJb3JpZ2luX2Vj|FwoGZXIvYXdzE)[A-Za-z0-9/+=]{8,})"
    ),
    "Slack token or webhook": (
        r"\bxox[abposr]-[A-Za-z0-9-]{10,}|\bhooks\.slack\.com/services/[A-Za-z0-9]+"
    ),
    "Google API key": r"(?-i:\bAIza[0-9A-Za-z_-]{35})",
    "JSON web token": r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}",
    "private key": r"BEGIN [A-Z ]*PRIVATE KEY",
}
GENERIC_LEAK_PATTERNS: dict[str, str] = {
    "this machine's home directory": re.escape(str(HOME)),
    "home directory path": r"/(?:local/home|home|Users)/[A-Za-z0-9_.-]+|\b[A-Z]:\\Users\\",
    "AWS account number": (
        rf"\b(?!(?:{_EXAMPLE_ACCOUNT})\b)\d{{12}}\b|\b\d{{4}}-\d{{4}}-\d{{4}}\b"
    ),
    "ARN": rf"\barn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:(?!(?:{_EXAMPLE_ACCOUNT}):)[^\s\"'`)]*",
    "S3 bucket": r"\bs3://(?!bucket(?![\w.-]))[a-z0-9][a-z0-9.-]*",
    "internal hostname": (
        r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:corp|internal|intranet|lan|localdomain)\b(?![.-]?\w)"
        r"|\b[a-z0-9-]+\.(?:corp|internal|intranet)\.[a-z0-9-]+"
        r"|\b(?:ip|ec2)-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}\b"
    ),
    "intranet URL": (
        r"\bhttps?://(?!localhost\b)[a-z0-9-]+(?![a-z0-9.-])"
        r"|(?<![\w/.-])go/(?!no-go\b)[a-z0-9_-]+"
    ),
    "email address": (
        rf"(?<![\w.%+-])(?!{re.escape(PUBLIC_EMAIL)}\b|(?:noreply|git)@github\.com\b)"
        r"[a-z0-9._%+-]+@(?!(?:[a-z0-9-]+\.)*(?:example\.(?:com|net|org)|example|test|invalid"
        r"|localhost)\b)[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b"
    ),
    "IP address": (
        rf"\b(?!(?:127|0|169\.254|255|192\.0\.2|198\.51\.100|203\.0\.113)\.)"
        rf"{_OCTET}(?:\.{_OCTET}){{3}}\b"
    ),
}
EVERGREEN_PATHS = re.compile(
    r"(?:AGENTS|README)\.md|instructions/[^/]+\.md|claude/agents/[^/]+\.md"
    r"|claude/skills/[^/]+/(?:references/)?[^/]+\.md"
)
EVERGREEN_PATTERNS: dict[str, str] = {
    "date": (
        r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?\b"
        r"|\b(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\b"
        r"|(?<![\d-])(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b"
        r"|\b\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b"
        rf"|(?-i:\b{_MONTH}\.? \d{{1,2}}(?:st|nd|rd|th)?\b|\b\d{{1,2}}(?:st|nd|rd|th)? {_MONTH}\b"
        rf"|\b{_MONTH},? (?:19|20)\d{{2}}\b|\b{_WEEKDAY},? (?:\d|{_MONTH}))"
    ),
    "history wording": (
        rf"\bas of\b|\bsince (?:v?\d|last\b|(?-i:{_MONTH})\b)"
        r"|\b(?:previously|formerly|originally|historically)\b|\bchange ?log\b|\brelease notes\b"
        r"|(?<!\bis )(?<!\bare )(?<!\bbe )(?<!\bwas )(?<!\bwere )(?<!\bbeen )(?<!\bget )\bused to\b"
    ),
    "ticket or task ID": r"(?-i:\b(?:TASK|BUG|ISSUE|TICKET|PR|CR)-\d+\b)",
    "commit hash or UUID": (
        r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"
        r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
    ),
}
# A date inside a link names the page it points to, not the history of a rule.
URL = re.compile(r"\bhttps?://\S+")
# A \b in a leak pattern also fires between a letter or digit and an underscore, so a name inside an identifier matches.
WORD_BOUNDARY = re.compile(r"(?<!\\)\\b")
IDENTIFIER_BOUNDARY = r"(?:\b|(?<=_)(?=[^\W_])|(?<=[^\W_])(?=_))"
# Without its leading \b a pattern matches a superset of lines, and re finds the literal that follows fast.
LEADING_BOUNDARY = re.compile(r"^((?:\(\?[a-zA-Z-]+:)?)\\b")
Patterns = dict[str, tuple[re.Pattern[str], re.Pattern[str]]]
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".git", ".private"}


def load_private_replacements() -> list[tuple[str, str]]:
    rows = [
        line.split("\t")
        for line in PRIVATE_REPLACEMENTS_FILE.read_text().splitlines()
        if line.strip()
    ]
    malformed_rows = [row for row in rows if len(row) != 2]
    if malformed_rows:
        raise ValueError(
            f"{PRIVATE_REPLACEMENTS_FILE} rows must be old<TAB>new, got {malformed_rows}"
        )
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


def compile_patterns(patterns: dict[str, str], boundary: str = r"\b") -> Patterns:
    """Each pattern, with its word boundaries replaced by `boundary`, as (prefilter, full pattern)."""
    compiled = {}
    for label, pattern in patterns.items():
        prefilter = LEADING_BOUNDARY.sub(r"\1", pattern)
        compiled[label] = (
            re.compile(WORD_BOUNDARY.sub(lambda _: boundary, prefilter), re.IGNORECASE),
            re.compile(WORD_BOUNDARY.sub(lambda _: boundary, pattern), re.IGNORECASE),
        )
    return compiled


PUBLIC_LEAK_PATTERNS = compile_patterns(
    {**SECRET_PATTERNS, **GENERIC_LEAK_PATTERNS}, IDENTIFIER_BOUNDARY
)
EVERGREEN_TEXT_PATTERNS = compile_patterns(EVERGREEN_PATTERNS)


def load_leak_patterns() -> Patterns:
    """The generic leak classes and the private names, each keyed by the label a finding reports."""
    private_patterns = [
        line for line in PRIVATE_PATTERNS_FILE.read_text().splitlines() if line.strip()
    ]
    if not private_patterns:
        raise ValueError(
            f"{PRIVATE_PATTERNS_FILE} is empty; it must list the private names to check for"
        )
    private = compile_patterns(
        {f"private pattern {pattern!r}": pattern for pattern in private_patterns},
        IDENTIFIER_BOUNDARY,
    )
    return {**PUBLIC_LEAK_PATTERNS, **private}


def load_allowed_matches() -> set[tuple[str, str]]:
    """The (path, matched text) pairs the scan lets through; a missing file lets nothing through."""
    if not PRIVATE_ALLOWED_MATCHES_FILE.exists():
        return set()
    rows = [
        line.split("\t")
        for line in PRIVATE_ALLOWED_MATCHES_FILE.read_text().splitlines()
        if line.strip()
    ]
    malformed_rows = [
        row for row in rows if len(row) != 3 or not all(field.strip() for field in row)
    ]
    if malformed_rows:
        raise ValueError(
            f"{PRIVATE_ALLOWED_MATCHES_FILE} rows must be path<TAB>matched text<TAB>reason, "
            f"got {malformed_rows}"
        )
    return {(path, text) for path, text, _reason in rows}


def git(*args: str) -> str:
    command = ["git", "-C", str(REPO_ROOT), *args]
    return subprocess.run(
        command, check=True, capture_output=True, encoding="utf-8", errors="replace"
    ).stdout


def findings(line: str, patterns: Patterns) -> list[tuple[str, str]]:
    """Each (label, matched text) that the patterns find in the line."""
    return [
        (label, match.group(0))
        for label, (prefilter, pattern) in patterns.items()
        if prefilter.search(line)
        for match in pattern.finditer(line)
    ]


def describe(label: str, text: str) -> str:
    return label if label in SECRET_PATTERNS else f"{label} {text!r}"


def file_line_leaks(
    relative: str,
    line: str,
    patterns: Patterns,
    allowed: set[tuple[str, str]],
) -> list[str]:
    return [
        describe(label, text)
        for label, text in findings(line, patterns)
        if (relative, text) not in allowed
    ]


def publishable_files() -> list[Path]:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return [
        REPO_ROOT / name for name in sorted(set(listed)) if name and (REPO_ROOT / name).is_file()
    ]


def scan_for_leaks() -> list[str]:
    """Leaks in every publishable file, and dates or history in its instruction and skill text."""
    leak_patterns = load_leak_patterns()
    allowed = load_allowed_matches()
    leaks = []
    for path in publishable_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        is_evergreen = EVERGREEN_PATHS.fullmatch(relative) is not None
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            found = file_line_leaks(relative, line, leak_patterns, allowed)
            if is_evergreen:
                found += file_line_leaks(
                    relative, URL.sub("", line), EVERGREEN_TEXT_PATTERNS, allowed
                )
            leaks += [f"{relative}:{line_number}: {finding}" for finding in found]
    return leaks


def scan_commits(commits: list[str]) -> list[str]:
    """Leaks in each commit's identities, message and added lines, so a leak a later commit deleted still counts.

    Dates and history wording are checked only in the tree: once a later commit removes them, they publish nothing.
    """
    leak_patterns = load_leak_patterns()
    allowed = load_allowed_matches()
    leaks = []
    for commit in commits:
        identities = git("log", "-1", "--format=author %an <%ae>%ncommitter %cn <%ce>", commit)
        for line in identities.splitlines():
            role = line.split(" ", 1)[0]
            leaks += [
                f"{commit} {role}: {describe(label, text)}"
                for label, text in findings(line, leak_patterns)
            ]
        for line_number, line in enumerate(
            git("log", "-1", "--format=%B", commit).splitlines(), start=1
        ):
            leaks += [
                f"{commit} message line {line_number}: {describe(label, text)}"
                for label, text in findings(line, leak_patterns)
            ]
        diff = git(
            "show",
            "--format=",
            "--unified=0",
            "--no-color",
            "--no-ext-diff",
            "--no-prefix",
            "--diff-merges=first-parent",
            commit,
        )
        path, in_hunk = "", False
        for line in diff.splitlines():
            if line.startswith("diff --git "):
                in_hunk = False
            elif line.startswith("@@"):
                in_hunk = True
            elif not in_hunk and line.startswith("+++ "):
                path = line[len("+++ ") :]
            elif in_hunk and line.startswith("+"):
                leaks += [
                    f"{commit} {path}: added line {finding}"
                    for finding in file_line_leaks(path, line[1:], leak_patterns, allowed)
                ]
    return leaks


def history_commits() -> list[str]:
    return git("rev-list", "--branches", "--tags", "--remotes").split()


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
    copies = [
        (HOME / source, REPO_ROOT / destination) for source, destination in COPIED_FILES.items()
    ]
    for source_dir, destination_dir in COPIED_DIRS.items():
        for source in sorted((HOME / source_dir).rglob("*")):
            if not source.is_dir() and not IGNORED_NAMES.intersection(source.parts):
                copies.append(
                    (source, REPO_ROOT / destination_dir / source.relative_to(HOME / source_dir))
                )
    return [
        (source, destination) for source, destination in copies if not is_repo_owned(destination)
    ]


def remove_stale_files(kept: set[Path]) -> None:
    """Delete files under the synced directories that are neither kept nor repo-owned, then the directories left empty."""
    destinations = [*COPIED_FILES.values(), *COPIED_DIRS.values()]
    for synced_dir in {
        Path(destination).parts[0] for destination in destinations if "/" in destination
    }:
        for path in sorted((REPO_ROOT / synced_dir).rglob("*"), reverse=True):
            if path in kept or is_repo_owned(path):
                continue
            if not path.is_dir():
                path.unlink()
            elif not any(path.iterdir()):
                path.rmdir()


def sync() -> None:
    copies = planned_copies()
    linked_paths = {
        destination for source, destination in copies if links_into_repo(source, destination)
    }
    written_paths = []
    for source, destination in copies:
        if destination not in linked_paths:
            copy_redacted(source, destination)
            written_paths.append(destination)

    codex_config_source = HOME / CODEX_CONFIG
    write_text(
        REPO_ROOT / "codex/config.toml",
        redact(sanitize_codex_config(codex_config_source.read_text())),
        codex_config_source,
    )
    codex_rules_source = HOME / CODEX_RULES
    write_text(
        REPO_ROOT / "codex/rules/default.rules",
        redact(keep_forbidden_codex_rules(codex_rules_source.read_text())),
        codex_rules_source,
    )
    written_paths += [REPO_ROOT / "codex/config.toml", REPO_ROOT / "codex/rules/default.rules"]

    remove_stale_files(set(written_paths) | linked_paths)
    fail_on_leaks(scan_for_leaks(), "fix the redaction before committing")
    logger.info("Synced %d files with no sensitive patterns found", len(written_paths))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy the shareable live config into this repo and scan it for leaks."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="only scan the repo for sensitive patterns; exit 1 on any match",
    )
    mode.add_argument(
        "--check-commits",
        nargs="+",
        metavar="SHA",
        help="scan each commit's identities, message and added lines; exit 1 on any match",
    )
    mode.add_argument(
        "--check-history",
        action="store_true",
        help="scan every commit on any branch, remote-tracking branch or tag; exit 1 on any match",
    )
    mode.add_argument(
        "--list-repo-owned",
        action="store_true",
        help="print each repo-owned path and its live path under ~, tab-separated",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.check:
        fail_on_leaks(scan_for_leaks(), "remove them before committing")
        logger.info("No sensitive patterns found")
    elif args.check_commits:
        fail_on_leaks(scan_commits(args.check_commits), "rewrite these commits before pushing")
        logger.info("No sensitive patterns found in %d commits", len(args.check_commits))
    elif args.check_history:
        commits = history_commits()
        fail_on_leaks(scan_commits(commits), "rewriting published history is the owner's call")
        logger.info("No sensitive patterns found in %d commits", len(commits))
    elif args.list_repo_owned:
        print("\n".join(f"{repo_path}\t{live_path}" for repo_path, live_path in REPO_OWNED.items()))
    else:
        sync()


if __name__ == "__main__":
    main()
