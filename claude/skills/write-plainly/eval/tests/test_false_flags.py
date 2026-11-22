import json
import os
import sys
from collections import Counter
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1]
FAKES_DIR = Path(__file__).resolve().parent / "fakes"
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(EVAL_DIR.parent))

import lint_prose

import false_flags

HUMAN_PUMP = (
    "The pump moves water from the tank to the field at night — the tank fills again by dawn."
    " Not only does the pump run quietly, it also uses little power. The valve opens when the"
    " float drops — nobody has to touch it.\n\n"
    "| part | job |\n| --- | --- |\n| pump | lifts water |\n\n"
    "- The filter keeps sand out of the pipe.\n"
)
HUMAN_WELL = (
    "Farmers in the valley share one well, and each family draws water on a set day. The rota has"
    " worked for years, and nobody can say exactly when it began. Disputes are rare because the"
    " schedule is posted at the well.\n"
)
HUMAN_LETTER = (
    "Dear Ana, the seeds arrived on time and the beans are already up. Thank you for the parcel"
    " and for the note about watering.\n"
)
AGENT_PUMP = (
    "The pump lifts water from the tank to the field each night — by dawn the tank is full again."
    " It draws exactly the power it needs and exactly no more. The float controls the valve, so"
    " nobody has to adjust it.\n"
)
AGENT_WELL = (
    "Families in the valley take turns at a single well, each on its own day of the week. The"
    " arrangement is old, and nobody knows exactly when it started. Quarrels are uncommon, since"
    " the schedule hangs beside the well.\n"
)
# (corpus, side, register, file name, text, words)
FIXTURES = (
    ("matched", "human", "techdoc", "human-pump.md", HUMAN_PUMP, 55),
    ("matched", "human", "essay", "human-well.md", HUMAN_WELL, 41),
    ("pages", "human", "letters", "human-letter.md", HUMAN_LETTER, 24),
    ("matched", "agent", "techdoc", "agent-pump.md", AGENT_PUMP, 41),
    ("matched", "agent", "essay", "agent-well.md", AGENT_WELL, 39),
)


def _launcher(directory: Path, name: str, script: Path) -> None:
    path = directory / name
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    path.chmod(0o755)


def _toml(config: dict) -> str:
    lines = [f"breakdown = {json.dumps(config['breakdown'])}"]
    for entry in config["file"]:
        lines += ["", "[[file]]", *(f"{key} = {json.dumps(value)}" for key, value in entry.items())]
    return "\n".join(lines) + "\n"


@pytest.fixture(autouse=True)
def fake_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _launcher(bin_dir, "sloplint", FAKES_DIR / "fake_sloplint.py")
    _launcher(bin_dir, "uvx", FAKES_DIR / "fake_slop_guard.py")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


@pytest.fixture
def paths(tmp_path: Path) -> dict[str, str]:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for _, _, _, name, text, _ in FIXTURES:
        (corpus_dir / name).write_text(text, encoding="utf-8")
    return {name: str(corpus_dir / name) for _, _, _, name, _, _ in FIXTURES}


@pytest.fixture
def config(paths: dict[str, str]) -> dict:
    entries = [
        {"name": corpus, "side": side, "register": register, "path": paths[name]}
        for corpus, side, register, name, _, _ in FIXTURES
    ]
    return {"breakdown": ["techdoc"], "file": entries}


@pytest.fixture
def texts(config: dict) -> list[false_flags.Text]:
    return false_flags.load_texts(config)


class TestLoadTexts:
    def test_counts_words_without_table_pipes_or_list_bullets(
        self, texts: list[false_flags.Text], paths: dict[str, str]
    ) -> None:
        loaded = [
            (t.key, t.corpus, t.side, t.register, t.words, t.markdown, t.rights) for t in texts
        ]
        assert loaded == [
            (paths[name], corpus, side, register, words, name == "human-pump.md", "")
            for corpus, side, register, name, _, words in FIXTURES
        ]


class TestCollectHits:
    def test_attributes_every_hit_to_its_text(
        self, texts: list[false_flags.Text], paths: dict[str, str]
    ) -> None:
        hits, catalogs = false_flags.collect_hits(texts)
        assert hits == {
            ("lint_prose", "em-dash"): Counter(
                {paths["human-pump.md"]: 2, paths["agent-pump.md"]: 1}
            ),
            ("sloplint", "exact-exactly"): Counter(
                {
                    paths["human-well.md"]: 1,
                    paths["agent-pump.md"]: 2,
                    paths["agent-well.md"]: 1,
                }
            ),
            ("slop-guard", "contrast_pairs"): Counter({paths["human-pump.md"]: 1}),
        }
        assert catalogs == {
            "lint_prose": set(lint_prose.MESSAGES),
            "sloplint": {"exact-exactly", "never-fires"},
            "slop-guard": {"contrast_pairs", "placeholder"},
        }


class TestRender:
    def test_reports_rates_ratios_register_columns_and_silent_rules(
        self, texts: list[false_flags.Text]
    ) -> None:
        hits, catalogs = false_flags.collect_hits(texts)
        lines = false_flags.render(texts, hits, catalogs, ["techdoc"], "versions").splitlines()
        corpora = lines.index("## Corpora") + 2
        assert lines[corpora : corpora + 10] == [
            "| side | register | texts | words | texts with markdown structure |",
            "|---|---|---|---|---|",
            "| agent | essay | 1 | 39 | 0 |",
            "| agent | techdoc | 1 | 41 | 0 |",
            "| human | essay | 1 | 41 | 0 |",
            "| human | letters | 1 | 24 | 0 |",
            "| human | techdoc | 1 | 55 | 1 |",
            "| **human total** |  | 3 | 120 | 1 |",
            "| **agent total** |  | 2 | 80 | 0 |",
            "",
        ]
        main_table = lines.index(
            "| rule | linter | human | agent | human / agent | human > agent"
            " | human docs | agent docs |"
        )
        assert lines[main_table + 2 : main_table + 6] == [
            "| contrast_pairs | slop-guard | 8.33 | 0.00 | inf | yes | 1/3 | 0/2 |",
            "| em-dash | lint_prose | 16.67 | 12.50 | 1.33 | yes | 1/3 | 1/2 |",
            "| exact-exactly | sloplint | 8.33 | 37.50 | 0.22 |  | 1/3 | 2/2 |",
            "",
        ]
        register_table = lines.index("## By corpus and register (hits per 1,000 words)") + 2
        assert lines[register_table : register_table + 6] == [
            (
                "| rule | linter | matched all human (96 w) | matched all agent (80 w)"
                " | techdoc human (55 w) | techdoc agent (41 w) |"
            ),
            "|---|---|---|---|---|---|",
            "| contrast_pairs | slop-guard | 10.42 | 0.00 | 18.18 | 0.00 |",
            "| em-dash | lint_prose | 20.83 | 12.50 | 36.36 | 24.39 |",
            "| exact-exactly | sloplint | 10.42 | 37.50 | 0.00 | 48.78 |",
            "",
        ]
        silent_lint_prose = ", ".join(sorted(set(lint_prose.MESSAGES) - {"em-dash"}))
        assert lines[-3:] == [
            f"- lint_prose: {silent_lint_prose}",
            "- sloplint: never-fires",
            "- slop-guard: placeholder",
        ]


class TestMain:
    def test_private_run_writes_under_dot_private_and_prints_nothing(
        self,
        tmp_path: Path,
        config: dict,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert false_flags.PRIVATE_OUTPUT.is_relative_to(false_flags.REPO_ROOT / ".private")
        public = {"breakdown": [], "file": config["file"][:3]}
        private = {"breakdown": config["breakdown"], "file": config["file"][3:]}
        (tmp_path / "public.toml").write_text(_toml(public), encoding="utf-8")
        (tmp_path / "private.toml").write_text(_toml(private), encoding="utf-8")
        output = tmp_path / ".private" / "eval" / "false-flags-private.md"
        output.parent.mkdir(parents=True)
        monkeypatch.setattr(false_flags, "PUBLIC_CORPORA", tmp_path / "public.toml")
        monkeypatch.setattr(false_flags, "PRIVATE_CORPORA", tmp_path / "private.toml")
        monkeypatch.setattr(false_flags, "PRIVATE_OUTPUT", output)
        monkeypatch.setattr(false_flags, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", ["false_flags.py", "--private"])

        false_flags.main()

        assert capsys.readouterr().out == ""
        report = output.read_text(encoding="utf-8")
        modules = (
            "lint_prose.py, lint_prose_document.py, lint_prose_markdown.py, lint_prose_patterns.py"
        )
        assert f"{modules} sha256 " in report.splitlines()[2]
        assert "| **agent total** |  | 2 | 80 | 0 |" in report
        assert "| techdoc agent (41 w) |" in report
        assert (tmp_path / "rights.tsv").read_text(
            encoding="utf-8"
        ) == false_flags.RIGHTS_HEADER + "\n"
