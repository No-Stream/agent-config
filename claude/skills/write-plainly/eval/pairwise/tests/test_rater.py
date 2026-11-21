from __future__ import annotations

import html
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from rater import (
    GRADE_POINTS,
    GRADES_FILE_NAME,
    LineRefused,
    build_page,
    latest_grades,
    load_sets,
    record,
    render_passage,
    sets_digest,
)

RATER_SCRIPT = Path(__file__).resolve().parents[1] / "rater.py"
LETTERS = ("A", "B", "C")
PIPELINES = ("kestrel-pipeline", "osprey-pipeline", "plover-pipeline")


def make_set(set_id: str) -> dict:
    return {
        "set_id": set_id,
        "doc_type": "README section",
        "reader": "Ana, who asks <why> & how",
        "passages": {
            letter: f'Passage {letter} of set {set_id} says 5 < 6 & "quotes" stay.'
            for letter in LETTERS
        },
    }


@pytest.fixture
def sets_file(tmp_path: Path) -> Path:
    """Three sets of three passages, with a key beside them naming the pipelines."""
    path = tmp_path / "sets.jsonl"
    path.write_text("".join(json.dumps(make_set(set_id)) + "\n" for set_id in ("1", "2", "3")))
    key = {"sets": {set_id: dict(zip(LETTERS, PIPELINES)) for set_id in ("1", "2", "3")}}
    (tmp_path / "key.json").write_text(json.dumps(key))
    return path


def line(sets_file: Path, sets: str, notes: dict | None = None) -> str:
    return f"wp1 {sets_digest(sets_file)} {sets} notes={json.dumps(notes or {})}"


def grades_on_disk(sets_file: Path) -> dict[str, dict]:
    return latest_grades(sets_file.parent / GRADES_FILE_NAME)


class TestRender:
    def test_paragraphs_and_inline_code_with_everything_escaped(self) -> None:
        rendered = render_passage("Run `a<b>` now.\nStill <b>one</b> paragraph.\n\nSecond.")
        assert rendered == (
            "<p>Run <code>a&lt;b&gt;</code> now. Still &lt;b&gt;one&lt;/b&gt; paragraph.</p>"
            "<p>Second.</p>"
        )

    def test_a_paragraph_then_bullet_and_numbered_lists(self) -> None:
        rendered = render_passage("Steps:\n- one\n  continued\n* two\n\n1. first\n2. second")
        assert rendered == (
            "<p>Steps:</p><ul><li>one continued</li><li>two</li></ul>"
            "<ol><li>first</li><li>second</li></ol>"
        )

    def test_a_table_needs_its_separator_row(self) -> None:
        rendered = render_passage("| Change | Gain |\n| :--- | ---: |\n| `cap` | +0.2% |")
        assert rendered == (
            '<div class="table"><table><thead><tr><th>Change</th><th>Gain</th></tr></thead>'
            "<tbody><tr><td><code>cap</code></td><td>+0.2%</td></tr></tbody></table></div>"
        )
        assert render_passage("| not | a table |\n| just pipes |") == (
            "<p>| not | a table | | just pipes |</p>"
        )

    def test_fenced_code_keeps_its_lines_and_blank_lines(self) -> None:
        rendered = render_passage("Before.\n\n```\n(-inf, 0] u [1, inf)\n\n<x>\n```\n\nAfter.")
        assert rendered == (
            "<p>Before.</p><pre><code>(-inf, 0] u [1, inf)\n\n&lt;x&gt;</code></pre><p>After.</p>"
        )

    def test_an_unpaired_backtick_and_other_markdown_show_as_typed(self) -> None:
        assert render_passage("A ` alone, **bold** and # hash.") == (
            "<p>A ` alone, **bold** and # hash.</p>"
        )


class TestBuild:
    def test_the_page_holds_every_passage_escaped_and_no_pipeline_name(
        self, sets_file: Path
    ) -> None:
        page = build_page(load_sets(sets_file), sets_digest(sets_file))
        for passage_set in load_sets(sets_file):
            assert html.escape(passage_set["reader"]) in page
            for text in passage_set["passages"].values():
                assert f"<p>{html.escape(text)}</p>" in page
        assert "<why>" not in page and "5 < 6" not in page
        assert not [name for name in PIPELINES if name in page]
        assert page.count('<section class="task"') == 3
        assert page.count("data-grade=") == 3 * 3 * len(GRADE_POINTS)

    def test_the_page_carries_the_digest_set_ids_and_letters_for_the_result_line(
        self, sets_file: Path
    ) -> None:
        page = build_page(load_sets(sets_file), sets_digest(sets_file))
        meta_text = page.split('id="rater-meta">', 1)[1].split("</script>", 1)[0]
        assert json.loads(meta_text) == {
            "version": "wp1",
            "digest": sets_digest(sets_file),
            "sets": [{"id": set_id, "letters": list(LETTERS)} for set_id in ("1", "2", "3")],
        }

    def test_the_command_writes_the_page(self, sets_file: Path) -> None:
        out = sets_file.parent / "rater.html"
        completed = subprocess.run(
            [sys.executable, str(RATER_SCRIPT), "build", str(sets_file), "--out", str(out)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert out.read_text() == build_page(load_sets(sets_file), sets_digest(sets_file))
        assert sets_digest(sets_file) in completed.stdout


class TestRecord:
    def test_a_line_round_trips_to_one_record_per_set_with_its_note(self, sets_file: Path) -> None:
        note = 'B is padded, C "fine" | notes={} ü'
        assert record(sets_file, line(sets_file, "1:B+,A-,F 3:A,A,C-", {"3": note})) == ["1", "3"]
        on_disk = grades_on_disk(sets_file)
        assert {set_id: (r["grades"], r["note"]) for set_id, r in on_disk.items()} == {
            "1": ({"A": "B+", "B": "A-", "C": "F"}, ""),
            "3": ({"A": "A", "B": "A", "C": "C-"}, note),
        }
        assert all(r["recorded_at"].endswith("+00:00") for r in on_disk.values())

    def test_a_later_line_replaces_its_sets_and_keeps_the_others(self, sets_file: Path) -> None:
        record(sets_file, line(sets_file, "1:B,B,B 2:C,C,C", {"1": "first try"}))
        record(sets_file, line(sets_file, "3:D,D,D 1:A,B,C"))
        on_disk = grades_on_disk(sets_file)
        assert list(on_disk) == ["1", "2", "3"]
        assert on_disk["1"]["grades"] == {"A": "A", "B": "B", "C": "C"}
        assert on_disk["1"]["note"] == ""
        assert on_disk["2"]["grades"] == {"A": "C", "B": "C", "C": "C"}
        lines = (sets_file.parent / GRADES_FILE_NAME).read_text().splitlines()
        assert len(lines) == 3

    @pytest.mark.parametrize(
        ("made", "message"),
        [
            ("wp2 {digest} 1:A,B,C notes={{}}", "does not start with wp1"),
            ("wp1 0000beef 1:A,B,C notes={{}}", "not for this sets file"),
            ("wp1 1:A,B,C notes={{}}", "not for this sets file"),
            ("wp1 {digest} 9:A,B,C notes={{}}", "no set '9'"),
            ("wp1 {digest} 1:A,B,C 1:A,B,C notes={{}}", "appears twice"),
            ("wp1 {digest} 1:A,B notes={{}}", "2 grades for 3 passages"),
            ("wp1 {digest} 1:A,E,F+ notes={{}}", "not grades"),
            ("wp1 {digest} 1:A,b,C notes={{}}", "not grades"),
            ("wp1 {digest} 1:A,B,C", "no notes= part"),
            ('wp1 {digest} 1:A,B,C notes={{"1":"half a no', "not JSON"),
            ('wp1 {digest} 1:A,B,C notes=["1"]', "not an object"),
            ('wp1 {digest} 1:A,B,C notes={{"2":"x"}}', "does not grade"),
            ("wp1 {digest} notes={{}}", "grades no task"),
        ],
    )
    def test_a_malformed_line_is_refused_and_nothing_is_written(
        self, sets_file: Path, made: str, message: str
    ) -> None:
        with pytest.raises(LineRefused, match=message):
            record(sets_file, made.format(digest=sets_digest(sets_file)))
        assert not (sets_file.parent / GRADES_FILE_NAME).exists()

    def test_a_line_from_another_sets_file_is_refused(
        self, sets_file: Path, tmp_path: Path
    ) -> None:
        other = tmp_path / "other" / "sets.jsonl"
        other.parent.mkdir()
        other.write_text(sets_file.read_text().replace("Passage A of set 1", "Passage A, edited"))
        with pytest.raises(LineRefused, match="not for this sets file"):
            record(other, line(sets_file, "1:A,B,C"))

    def test_the_command_exits_non_zero_with_the_reason(self, sets_file: Path) -> None:
        completed = subprocess.run(
            [sys.executable, str(RATER_SCRIPT), "record", str(sets_file)],
            input="wp1 nope notes={}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 1
        assert "refused: the line is not for this sets file" in completed.stderr

    def test_the_documented_heredoc_records_a_note_with_quotes_a_pipe_and_an_apostrophe(
        self, sets_file: Path
    ) -> None:
        note = 'B\'s "lead" is padded | C is fine'
        result_line = line(sets_file, "2:A,A,B", {"2": note})
        arguments = (sys.executable, str(RATER_SCRIPT), "record", str(sets_file))
        command = f"{shlex.join(arguments)} <<'EOF'\n{result_line}\nEOF\n"
        completed = subprocess.run(
            ["sh", "-c", command], capture_output=True, text=True, check=True
        )
        assert "recorded sets 2" in completed.stdout and "1 of 3 sets graded" in completed.stdout
        assert grades_on_disk(sets_file)["2"]["grades"] == {"A": "A", "B": "A", "C": "B"}
        assert grades_on_disk(sets_file)["2"]["note"] == note
