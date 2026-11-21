"""The grading page's script in headless Chromium, served under the sandbox header it ships with."""

from __future__ import annotations

import functools
import http.server
import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from rater import GRADES_FILE_NAME, build_page, latest_grades, load_sets, sets_digest

sync_api = pytest.importorskip("playwright.sync_api")

RATER_SCRIPT = Path(__file__).resolve().parents[1] / "rater.py"
SANDBOX_POLICY = "sandbox allow-scripts"
VISIBLE_TASK = "section.task:not([hidden])"
NOTE = 'B\'s "lead" is padded | notes={} ü'


class SandboxedHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", SANDBOX_POLICY)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


@pytest.fixture(scope="module")
def browser() -> Iterator[sync_api.Browser]:
    with sync_api.sync_playwright() as playwright:
        chromium = playwright.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def page_url(sets_file: Path) -> Iterator[str]:
    """The page built from the sets fixture, served from the sets file's directory."""
    page_file = sets_file.parent / "rater.html"
    page_file.write_text(build_page(load_sets(sets_file), sets_digest(sets_file)))
    handler = functools.partial(SandboxedHandler, directory=str(sets_file.parent))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/{page_file.name}"
    server.shutdown()
    server.server_close()


class Grader:
    """One tab of the page, failing on any script error."""

    def __init__(self, page: sync_api.Page) -> None:
        self.page = page
        self.errors: list[str] = []
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.on(
            "console",
            lambda message: self.errors.append(message.text) if message.type == "error" else None,
        )

    def grade(self, letter: str, grade: str) -> None:
        selector = f'{VISIBLE_TASK} article[data-letter="{letter}"] button[data-grade="{grade}"]'
        self.page.locator(selector).click()

    def pressed(self) -> dict[str, str]:
        return self.page.evaluate(
            """(task) => Object.fromEntries(
                Array.from(document.querySelectorAll(task + ' article.passage')).map((article) => [
                    article.dataset.letter,
                    (article.querySelector('button[aria-pressed="true"]') || {}).textContent || '',
                ]))""",
            VISIBLE_TASK,
        )

    def heading(self) -> str:
        return self.page.locator(f"{VISIBLE_TASK} h1").inner_text()

    def line(self) -> str:
        return self.page.locator("#result-line").input_value()


def test_grades_and_a_note_survive_reloads_and_reach_grades_jsonl(
    browser: sync_api.Browser, page_url: str, sets_file: Path
) -> None:
    context = browser.new_context()
    grader = Grader(context.new_page())
    page = grader.page
    response = page.goto(page_url)
    assert response.headers["content-security-policy"] == SANDBOX_POLICY
    assert page.evaluate("self.origin") == "null"
    digest = sets_digest(sets_file)
    assert grader.line() == f"wp1 {digest} notes={{}}"

    for letter, grade in zip("ABC", ("B+", "A-", "F")):
        grader.grade(letter, grade)
    grader.grade("C", "F")
    assert grader.pressed() == {"A": "B+", "B": "A-", "C": ""}
    grader.grade("C", "C-")
    grader.grade("A", "A")
    assert grader.pressed() == {"A": "A", "B": "A-", "C": "C-"}
    page.locator(f"{VISIBLE_TASK} input[data-note]").fill(NOTE)

    page.locator(f"{VISIBLE_TASK} button[data-step='1']").click()
    assert grader.heading() == "Task 2 of 3"
    grader.grade("A", "D")
    page.locator("nav.tasks button[data-go='2']").click()
    assert grader.heading() == "Task 3 of 3"
    for letter, grade in zip("ABC", ("D+", "B", "A+")):
        grader.grade(letter, grade)
    assert page.locator("#graded-count").inner_text() == "Graded 7 of 9"
    notes = json.dumps({"1": NOTE}, ensure_ascii=False, separators=(",", ":"))
    expected_line = f"wp1 {digest} 1:A,A-,C- 3:D+,B,A+ notes={notes}"
    assert grader.line() == expected_line

    hashed_url = page.url
    page.reload()
    assert grader.heading() == "Task 3 of 3" and grader.line() == expected_line
    page.goto(page_url)
    assert grader.line() == expected_line, "window.name alone restores the grades"
    new_tab = Grader(context.new_page())  # a new tab starts with an empty window.name
    new_tab.page.goto(hashed_url)
    assert new_tab.line() == expected_line, "the # fragment alone restores the grades"
    new_tab.page.locator("nav.tasks button[data-go='0']").click()
    assert new_tab.page.locator(f"{VISIBLE_TASK} input[data-note]").input_value() == NOTE
    assert grader.errors == [] and new_tab.errors == []
    context.close()

    subprocess.run(
        [sys.executable, str(RATER_SCRIPT), "record", str(sets_file)],
        input=expected_line + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    on_disk = latest_grades(sets_file.parent / GRADES_FILE_NAME)
    assert {set_id: (record["grades"], record["note"]) for set_id, record in on_disk.items()} == {
        "1": ({"A": "A", "B": "A-", "C": "C-"}, NOTE),
        "3": ({"A": "D+", "B": "B", "C": "A+"}, ""),
    }
