"""End-to-end tests of sync.py and scripts/link-repo-owned.sh against a temporary home and repo."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE_REPO = Path(__file__).resolve().parents[1]
REPO_OWNED_FILES = (
    "claude/skills/write-plainly/SKILL.md",
    "claude/skills/write-plainly/tests/test_lint_prose.py",
    "claude/agents/prose-reviewer.md",
    "claude/agents/prose-fidelity-checker.md",
    "claude/agents/prose-reader-test.md",
)
LIVE_REPO_OWNED_PATHS = (
    ".claude/skills/write-plainly",
    ".claude/agents/prose-reviewer.md",
    ".claude/agents/prose-fidelity-checker.md",
    ".claude/agents/prose-reader-test.md",
)
BACKUP_ROOT = ".local/state/agent-config-backups"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A live config with every path sync.py copies."""
    home = tmp_path / "home"
    write(home / "AGENTS.md", f"Notes live in {home}/notes and Secret Project is private.\n")
    write(home / ".claude/settings.json", '{"model": "opus"}\n')
    write(home / ".claude/statusline-command.sh", "echo status\n")
    write(home / ".claude/hooks/guard-bash.sh", "exit 0\n")
    write(home / ".codex/hooks/guard_shell.py", "print('guard')\n")
    write(home / ".codex/hooks/guard_shell_cases.tsv", "ALLOW\tls\n")
    write(home / ".codex/hooks/test_guard_shell.sh", "exit 0\n")
    write(home / ".claude/agents/codex-reviewer.md", "live codex reviewer\n")
    write(
        home / ".claude/agents/prose-reviewer.md",
        "live prose reviewer that must not reach the repo\n",
    )
    write(
        home / ".claude/skills/write-plainly/SKILL.md",
        "live write-plainly that must not reach the repo\n",
    )
    write(home / ".claude/skills/paper-drafting/SKILL.md", "live paper drafting\n")
    write(home / ".claude/skills/review/SKILL.md", "live review\n")
    write(home / ".claude/skills/visualization/SKILL.md", "live visualization\n")
    write(
        home / ".codex/config.toml",
        'model = "gpt"\n\n[projects."/work/x"]\ntrust_level = "trusted"\n',
    )
    write(
        home / ".codex/rules/default.rules",
        '# rules\nprefix_rule(\n    pattern=["rm"],\n    decision="forbidden",\n)\n',
    )
    return home


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo on main with sync.py, the link script, the private lists, and repo-owned files.

    The repo-owned files differ from their live copies in the home fixture.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(SOURCE_REPO / "sync.py", repo / "sync.py")
    write(repo / ".gitignore", ".private/\ncache/\n")
    write(repo / ".private/forbidden_patterns.txt", "\\bExampleCorp\\b\n")
    write(repo / ".private/replacements.tsv", "Secret Project\tthe project\n")
    for relative in REPO_OWNED_FILES:
        write(repo / relative, f"repo copy of {relative}\n")
    (repo / "scripts").mkdir()
    shutil.copy2(SOURCE_REPO / "scripts/link-repo-owned.sh", repo / "scripts/link-repo-owned.sh")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    return repo


@pytest.fixture
def empty_home(tmp_path: Path) -> Path:
    """A home directory with no live config, as on a machine that only checks the repo."""
    empty_home = tmp_path / "unrelated-home"
    empty_home.mkdir()
    return empty_home


def commit(repo: Path, message: str, path: str) -> str:
    subprocess.run(["git", "-C", str(repo), "add", "--", path], check=True)
    identity = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]
    subprocess.run(
        ["git", "-C", str(repo), *identity, "commit", "-q", "-m", message, "--", path], check=True
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def run_sync(repo: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "sync.py"), *args],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


def run_link_script(repo: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "scripts/link-repo-owned.sh"), *args],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


class TestSync:
    def test_leaves_repo_owned_files_byte_identical(self, repo: Path, home: Path) -> None:
        (home / ".claude/agents/prose-fidelity-checker.md").symlink_to(
            repo / "claude/agents/prose-fidelity-checker.md"
        )
        before = {relative: (repo / relative).read_bytes() for relative in REPO_OWNED_FILES}

        result = run_sync(repo, home)

        assert result.returncode == 0, result.stderr
        assert {relative: (repo / relative).read_bytes() for relative in REPO_OWNED_FILES} == before

    def test_copies_redacts_and_prunes_everything_else(self, repo: Path, home: Path) -> None:
        write(repo / "claude/skills/review/stale.md", "deleted from the live config\n")

        result = run_sync(repo, home)

        assert result.returncode == 0, result.stderr
        agents = (repo / "AGENTS.md").read_text()
        assert agents == "Notes live in ~/notes and the project is private.\n"
        assert (repo / "claude/agents/codex-reviewer.md").read_text() == "live codex reviewer\n"
        assert (repo / "claude/skills/visualization/SKILL.md").read_text() == "live visualization\n"
        assert (repo / "codex/hooks/guard_shell_cases.tsv").read_text() == "ALLOW\tls\n"
        assert "projects" not in (repo / "codex/config.toml").read_text()
        assert not (repo / "claude/skills/review/stale.md").exists()

    def test_leaves_paths_behind_a_live_symlink_into_the_repo_alone(
        self, repo: Path, home: Path
    ) -> None:
        linked_files = ("claude/skills/visualization/SKILL.md", "claude/hooks/guard-bash.sh")
        # Redaction rewrites Secret Project, so copying a linked file onto itself would change it.
        for relative in linked_files:
            write(repo / relative, f"repo copy of {relative} for Secret Project\n")
        before = {relative: (repo / relative).read_bytes() for relative in linked_files}
        shutil.rmtree(home / ".claude/skills/visualization")
        (home / ".claude/skills/visualization").symlink_to(repo / "claude/skills/visualization")
        (home / ".claude/hooks/guard-bash.sh").unlink()
        (home / ".claude/hooks/guard-bash.sh").symlink_to(repo / "claude/hooks/guard-bash.sh")

        result = run_sync(repo, home)

        assert result.returncode == 0, result.stderr
        assert {relative: (repo / relative).read_bytes() for relative in linked_files} == before


class TestCheck:
    def test_fails_on_a_planted_leak_and_passes_once_it_is_removed(
        self, repo: Path, empty_home: Path
    ) -> None:
        write(repo / "claude/notes.md", "nothing to see\n")
        (repo / "cache").mkdir()
        (repo / "cache/corpus.gz").write_bytes(b"\x1f\x8b binary cache that mentions ExampleCorp\n")
        assert run_sync(repo, empty_home, "--check").returncode == 0

        write(repo / "claude/notes.md", "nothing to see\nbuilt for ExampleCorp\n")
        planted = run_sync(repo, empty_home, "--check")
        assert planted.returncode == 1
        assert "claude/notes.md:2" in planted.stderr

        write(repo / "claude/notes.md", "nothing to see\n")
        assert run_sync(repo, empty_home, "--check").returncode == 0


class TestCheckCommits:
    def test_fails_on_a_leak_that_a_later_commit_removed(
        self, repo: Path, empty_home: Path
    ) -> None:
        write(repo / "notes.md", "nothing to see\n")
        clean = commit(repo, "Add notes", "notes.md")
        write(repo / "notes.md", "nothing to see\nbuilt for ExampleCorp\n")
        leaking = commit(repo, "Expand notes", "notes.md")
        write(repo / "notes.md", "nothing to see\n")
        removing = commit(repo, "Trim notes", "notes.md")
        assert run_sync(repo, empty_home, "--check").returncode == 0

        result = run_sync(repo, empty_home, "--check-commits", clean, leaking, removing)

        assert result.returncode == 1
        assert f"{leaking} notes.md" in result.stderr
        assert run_sync(repo, empty_home, "--check-commits", clean, removing).returncode == 0

    def test_fails_on_a_leak_in_a_commit_message(self, repo: Path, empty_home: Path) -> None:
        write(repo / "notes.md", "nothing to see\n")
        sha = commit(repo, "Add notes for the ExampleCorp launch", "notes.md")

        result = run_sync(repo, empty_home, "--check-commits", sha)

        assert result.returncode == 1
        assert f"{sha} message" in result.stderr


class TestLinkRepoOwned:
    def test_links_every_repo_owned_path_and_reruns_cleanly(
        self, repo: Path, tmp_path: Path
    ) -> None:
        home = tmp_path / "fresh-home"
        home.mkdir()

        first, second = run_link_script(repo, home), run_link_script(repo, home)

        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        for live in LIVE_REPO_OWNED_PATHS:
            assert (home / live).is_symlink()
            assert (home / live).resolve() == (repo / live.lstrip(".")).resolve()
        assert not (home / BACKUP_ROOT).exists()

    def test_refuses_to_link_into_a_checkout_that_is_not_on_main(
        self, repo: Path, tmp_path: Path
    ) -> None:
        home = tmp_path / "fresh-home"
        home.mkdir()
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feature"], check=True)

        result = run_link_script(repo, home)

        assert result.returncode != 0
        assert "feature" in result.stderr
        assert not any(home.iterdir())

    def test_backs_up_an_identical_live_copy_before_linking(
        self, repo: Path, tmp_path: Path
    ) -> None:
        home = tmp_path / "home-with-copy"
        shutil.copytree(repo / "claude/skills/write-plainly", home / ".claude/skills/write-plainly")

        result = run_link_script(repo, home)

        assert result.returncode == 0, result.stderr
        assert (home / ".claude/skills/write-plainly").is_symlink()
        assert [path.name for path in (home / ".claude/skills").iterdir()] == ["write-plainly"]
        [backup] = home.glob(f"{BACKUP_ROOT}/*/.claude/skills/write-plainly")
        assert snapshot(backup) == snapshot(repo / "claude/skills/write-plainly")

    def test_stops_with_the_diff_when_the_live_copy_differs(
        self, repo: Path, tmp_path: Path
    ) -> None:
        home = tmp_path / "home-with-edit"
        write(home / ".claude/agents/prose-reviewer.md", "an unsynced live edit\n")

        result = run_link_script(repo, home)

        assert result.returncode != 0
        assert "an unsynced live edit" in result.stdout
        assert "rerun with --replace" in result.stderr
        assert not (home / ".claude/agents/prose-reviewer.md").is_symlink()
        assert (home / ".claude/agents/prose-reviewer.md").read_text() == "an unsynced live edit\n"
        assert not (home / BACKUP_ROOT).exists()

    def test_replace_backs_up_a_differing_live_copy_and_links(
        self, repo: Path, tmp_path: Path
    ) -> None:
        home = tmp_path / "home-with-edit"
        write(home / ".claude/agents/prose-reviewer.md", "an unsynced live edit\n")
        write(home / ".claude/skills/write-plainly/SKILL.md", "an older live skill\n")

        result = run_link_script(repo, home, "--replace")

        assert result.returncode == 0, result.stderr
        for live in LIVE_REPO_OWNED_PATHS:
            assert (home / live).resolve() == (repo / live.lstrip(".")).resolve()
        [backup] = home.glob(f"{BACKUP_ROOT}/*")
        assert snapshot(backup) == {
            ".claude/agents/prose-reviewer.md": b"an unsynced live edit\n",
            ".claude/skills/write-plainly/SKILL.md": b"an older live skill\n",
        }

    def test_rejects_an_unknown_argument(self, repo: Path, tmp_path: Path) -> None:
        home = tmp_path / "fresh-home"
        home.mkdir()

        result = run_link_script(repo, home, "--force")

        assert result.returncode != 0
        assert "--force" in result.stderr
        assert not any(home.iterdir())
