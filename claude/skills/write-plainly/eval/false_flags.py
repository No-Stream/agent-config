#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["trafilatura==2.3.1"]
# ///
"""Compare prose lint hit rates on careful human prose and on agent drafts.

Fetches the corpora in corpora.toml into .cache/, runs lint_prose.py, sloplint and slop-guard on
every text, and prints each rule's hits per 1,000 words on the human and agent sides. A rule with
a higher human rate flags careful human writing more often than it flags model writing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import re
import subprocess
import sys
import tomllib
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lint_prose
import lint_prose_markdown

logger: logging.Logger = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parent
SKILL_DIR = EVAL_DIR.parent
REPO_ROOT = SKILL_DIR.parents[2]
CACHE_DIR = EVAL_DIR / ".cache"
PUBLIC_CORPORA = EVAL_DIR / "corpora.toml"
PRIVATE_DIR = REPO_ROOT / ".private" / "eval"
PRIVATE_CORPORA = PRIVATE_DIR / "corpora-private.toml"
PRIVATE_OUTPUT = PRIVATE_DIR / "false-flags-private.md"
LINT_PROSE_FILES = tuple(sorted(SKILL_DIR.glob("lint_prose*.py")))
SLOP_GUARD_VERSION = "0.5.0"
SLOP_GUARD = [
    "uvx",
    "--from",
    f"slop-guard=={SLOP_GUARD_VERSION}",
    "sg",
    "-j",
    "-c",
    str(SKILL_DIR / "slop-guard.jsonl"),
]
SLOPLINT_CHECK = ["sloplint", "-o", "json", "check", "--markdown"]
SIDES = ("human", "agent")
USER_AGENT = "Mozilla/5.0 (compatible; prose-lint-eval/1.0)"
MIN_PAGE_WORDS = 500
PUBLIC_DOMAIN_BEFORE_YEAR = 1929
RIGHTS_HEADER = "text\tside\tdate\tsource\trights"
MARKDOWN_STRUCTURE = re.compile(
    rf"^(#{{1,6}} |\s*{lint_prose_markdown.LIST_MARKER} )|\*\*", re.MULTILINE
)


@dataclass(frozen=True)
class Text:
    key: str
    corpus: str
    side: str
    register: str
    words: int
    markdown: bool
    rights: str


@dataclass(frozen=True)
class RuleRates:
    linter: str
    rule: str
    hits: Counter[str]
    human: float
    agent: float

    @property
    def ratio(self) -> float:
        return self.human / self.agent if self.agent else float("inf")


def _run(command: list[str], ok_codes: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode not in ok_codes:
        raise RuntimeError(f"{command[0]} exited {result.returncode}:\n{result.stderr}")
    return result.stdout


def _text(path: Path, corpus: str, side: str, register: str, rights: str) -> Text:
    """Load one text; `rights` is its rights.tsv row, empty for a local file."""
    if side not in SIDES:
        raise ValueError(f"{corpus}: side must be one of {SIDES}, got {side!r}")
    content = path.read_text(encoding="utf-8")
    words = len(lint_prose_markdown.WORD.findall(content))
    has_markdown = bool(MARKDOWN_STRUCTURE.search(content))
    return Text(str(path), corpus, side, register, words, has_markdown, rights)


def _page_text(page: dict) -> Text:
    html_path = CACHE_DIR / "pages" / f"{page['name']}.html"
    if not html_path.exists():
        logger.info(f"fetching {page['url']}")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(page["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            html_path.write_bytes(response.read())
    markdown = trafilatura.extract(
        html_path.read_bytes(),
        url=page["url"],
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=False,
    )
    if markdown is None or len(lint_prose_markdown.WORD.findall(markdown)) < MIN_PAGE_WORDS:
        raise ValueError(
            f"{page['url']} converted to under {MIN_PAGE_WORDS} words; check {html_path}"
        )
    text_path = html_path.with_suffix(".md")
    text_path.write_text(markdown + "\n", encoding="utf-8")
    rights = f"{page['name']}\t{page['side']}\t\t{page['url']}\tthe author's copyright"
    return _text(text_path, page["name"], page["side"], page["register"], rights)


def _checkout(pairs: dict) -> Path:
    """Check out only the index's directory (plus top-level files) of the pinned revision."""
    checkout = CACHE_DIR / pairs["name"]
    if not checkout.exists():
        logger.info(f"fetching {pairs['repo']} at {pairs['revision']}")
        partial = checkout.with_name(checkout.name + ".partial")
        git = ["git", "-C", str(partial)]
        _run(["git", "init", "-q", str(partial)])
        _run([*git, "sparse-checkout", "set", str(Path(pairs["index"]).parent)])
        _run([*git, "fetch", "-q", "--depth", "1", pairs["repo"], pairs["revision"]])
        _run([*git, "checkout", "-q", "FETCH_HEAD"])
        partial.rename(checkout)
    head = _run(["git", "-C", str(checkout), "rev-parse", "HEAD"]).strip()
    if head != pairs["revision"]:
        raise ValueError(f"{checkout} is at {head}, not {pairs['revision']}; delete it to refetch")
    return checkout


def _human_rights(date: str) -> str:
    if int(date.partition("-")[0]) < PUBLIC_DOMAIN_BEFORE_YEAR:
        return f"public domain in the US (published before {PUBLIC_DOMAIN_BEFORE_YEAR})"
    return "not stated by the corpus; treat as the author's copyright"


def _pair_texts(pairs: dict) -> list[Text]:
    index_path = _checkout(pairs) / pairs["index"]
    texts = []
    for pair in json.loads(index_path.read_text(encoding="utf-8"))["pairs"]:
        for index_side, side in pairs["sides"].items():
            record = pair[index_side]
            path = index_path.parent / record["file"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if not digest.startswith(record["sha256"]):
                raise ValueError(f"{path} does not match the sha256 in {index_path}")
            if side == "human":
                date, source = record["date"], record["source"]
                status = _human_rights(date)
            else:
                date, source = record["generated"], record["model"]
                status = "model output in an Apache-2.0 repository; no separate statement"
            rights = f"{pair['id']}/{index_side}\t{side}\t{date}\t{source}\t{status}"
            texts.append(_text(path, pairs["name"], side, pair["register"], rights))
    return texts


def _file_text(entry: dict) -> Text:
    path = REPO_ROOT / entry["path"]
    return _text(path, entry["name"], entry["side"], entry["register"], rights="")


def load_texts(config: dict) -> list[Text]:
    texts = [_page_text(page) for page in config.get("page", [])]
    for pairs in config.get("pairs", []):
        texts.extend(_pair_texts(pairs))
    texts.extend(_file_text(entry) for entry in config.get("file", []))
    return texts


def _lint_prose_hits(keys: list[str]) -> dict[str, Counter[str]]:
    return {
        key: Counter(
            finding.rule for finding in lint_prose.lint_text(Path(key).read_text(encoding="utf-8"))
        )
        for key in keys
    }


def _sloplint_hits(keys: list[str]) -> dict[str, Counter[str]]:
    notes_by_path = json.loads(_run([*SLOPLINT_CHECK, *keys], ok_codes=(0, 1)))
    hits: dict[str, Counter[str]] = {key: Counter() for key in keys}
    for path, notes in notes_by_path.items():
        hits[path].update(note["rule"] for note in notes)
    return hits


def _slop_guard_hits(keys: list[str]) -> dict[str, Counter[str]]:
    results = json.loads(_run([*SLOP_GUARD, *keys], ok_codes=(0, 1)))
    hits = {result["source"]: Counter(result["counts"]) for result in results}
    if set(hits) != set(keys):
        raise ValueError(
            "slop-guard returned results for a different set of files than it was given"
        )
    return hits


def _sloplint_rules() -> set[str]:
    catalog = json.loads(_run(["sloplint", "rules", "--json"]))
    return {rule["id"] for rule in catalog if rule["confidence"] != "low"}


def collect_hits(
    texts: list[Text],
) -> tuple[dict[tuple[str, str], Counter[str]], dict[str, set[str]]]:
    """Return hits per (linter, rule) per text key, and each linter's catalog of enabled rules."""
    keys = [text.key for text in texts]
    assert len(keys) > 1, "sloplint and slop-guard print a different JSON shape for one file"
    per_linter = {
        "lint_prose": _lint_prose_hits(keys),
        "sloplint": _sloplint_hits(keys),
        "slop-guard": _slop_guard_hits(keys),
    }
    catalogs = {
        "lint_prose": set(lint_prose.MESSAGES),
        "sloplint": _sloplint_rules(),
        "slop-guard": {rule for counts in per_linter["slop-guard"].values() for rule in counts},
    }
    hits: dict[tuple[str, str], Counter[str]] = {}
    for linter, by_key in per_linter.items():
        for key, counts in by_key.items():
            for rule, count in counts.items():
                if count:
                    hits.setdefault((linter, rule), Counter())[key] += count
    return hits, catalogs


def _rate(rule_hits: Counter[str], texts: list[Text]) -> float:
    return 1000 * sum(rule_hits[text.key] for text in texts) / sum(text.words for text in texts)


def _docs_hit(rule_hits: Counter[str], texts: list[Text]) -> str:
    return f"{sum(1 for text in texts if rule_hits[text.key])}/{len(texts)}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


def _corpus_row(texts: list[Text]) -> list[str]:
    words = sum(text.words for text in texts)
    return [str(len(texts)), f"{words:,}", str(sum(text.markdown for text in texts))]


def _corpus_table(texts: list[Text]) -> list[str]:
    cells = sorted({(text.side, text.register) for text in texts})
    rows = [
        [
            side,
            register,
            *_corpus_row([t for t in texts if (t.side, t.register) == (side, register)]),
        ]
        for side, register in cells
    ]
    for side in SIDES:
        rows.append([f"**{side} total**", "", *_corpus_row([t for t in texts if t.side == side])])
    return _table(["side", "register", "texts", "words", "texts with markdown structure"], rows)


def _groups(texts: list[Text], breakdown: list[str]) -> list[tuple[str, list[Text]]]:
    """Each corpus with agent texts, then each breakdown register, with its member texts."""
    paired = sorted({text.corpus for text in texts if text.side == "agent"})
    corpora = [(f"{corpus} all", [t for t in texts if t.corpus == corpus]) for corpus in paired]
    registers = [(register, [t for t in texts if t.register == register]) for register in breakdown]
    return corpora + registers


def render(
    texts: list[Text],
    hits: dict[tuple[str, str], Counter[str]],
    catalogs: dict[str, set[str]],
    breakdown: list[str],
    versions: str,
) -> str:
    by_side = {side: [text for text in texts if text.side == side] for side in SIDES}
    measured = sorted(
        (
            RuleRates(
                linter,
                rule,
                counts,
                _rate(counts, by_side["human"]),
                _rate(counts, by_side["agent"]),
            )
            for (linter, rule), counts in hits.items()
        ),
        key=lambda rates: (-rates.ratio, -rates.human),
    )

    main_rows = [
        [
            rates.rule,
            rates.linter,
            f"{rates.human:.2f}",
            f"{rates.agent:.2f}",
            f"{rates.ratio:.2f}",
            "yes" if rates.human > rates.agent else "",
            _docs_hit(rates.hits, by_side["human"]),
            _docs_hit(rates.hits, by_side["agent"]),
        ]
        for rates in measured
    ]

    columns = [
        (f"{label} {side} ({sum(t.words for t in members):,} w)", members)
        for label, group in _groups(texts, breakdown)
        for side in SIDES
        if (members := [text for text in group if text.side == side])
    ]
    register_rows = [
        [rates.rule, rates.linter, *(f"{_rate(rates.hits, members):.2f}" for _, members in columns)]
        for rates in measured
    ]

    fired = set(hits)
    never_fired = [
        f"- {linter}: {', '.join(sorted(r for r in catalog if (linter, r) not in fired)) or 'none'}"
        for linter, catalog in catalogs.items()
    ]
    lines = [
        "# Prose lint false-flag check",
        "",
        versions,
        "",
        "## Corpora",
        "",
        *_corpus_table(texts),
        "",
        "## Hits per 1,000 words",
        "",
        (
            "`human > agent` marks a rule whose human rate is above its agent rate. The docs columns "
            "count texts with at least one hit. A ratio of inf means the rule never fired on the agent side. "
            "A rule about headings, bold or lists can fire only on texts with markdown structure, so check "
            "that column of the corpus table before reading such a rule's agent rate."
        ),
        "",
        *_table(
            [
                "rule",
                "linter",
                "human",
                "agent",
                "human / agent",
                "human > agent",
                "human docs",
                "agent docs",
            ],
            main_rows,
        ),
        "",
        "## By corpus and register (hits per 1,000 words)",
        "",
        *_table(["rule", "linter", *(label for label, _ in columns)], register_rows),
        "",
        "## Enabled rules that never fired on any text",
        "",
        "These corpora say nothing about their false-flag rate.",
        "",
        *never_fired,
        "",
    ]
    return "\n".join(lines)


def _versions() -> str:
    lint_prose_bytes = b"".join(path.read_bytes() for path in LINT_PROSE_FILES)
    lint_prose_sha = hashlib.sha256(lint_prose_bytes).hexdigest()[:12]
    lint_prose_names = ", ".join(path.name for path in LINT_PROSE_FILES)
    sloplint_version = _run(["sloplint", "--version"]).strip()
    run_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Run {run_at}: {lint_prose_names} sha256 {lint_prose_sha}, "
        f"sloplint {sloplint_version}, "
        f"slop-guard {SLOP_GUARD_VERSION} with slop-guard.jsonl, "
        f"trafilatura {importlib.metadata.version('trafilatura')} for HTML conversion."
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private",
        action="store_true",
        help=f"add the corpora in {PRIVATE_CORPORA} and write the result to {PRIVATE_OUTPUT}",
    )
    options = parser.parse_args()
    configs = [tomllib.loads(PUBLIC_CORPORA.read_text(encoding="utf-8"))]
    if options.private:
        configs.append(tomllib.loads(PRIVATE_CORPORA.read_text(encoding="utf-8")))

    texts = [text for config in configs for text in load_texts(config)]
    rights = [RIGHTS_HEADER, *(text.rights for text in texts if text.rights)]
    (CACHE_DIR / "rights.tsv").write_text("\n".join(rights) + "\n", encoding="utf-8")
    breakdown = [register for config in configs for register in config["breakdown"]]
    hits, catalogs = collect_hits(texts)
    report = render(texts, hits, catalogs, breakdown, _versions())
    if options.private:
        PRIVATE_OUTPUT.write_text(report, encoding="utf-8")
        logger.info(f"wrote {PRIVATE_OUTPUT}")
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
