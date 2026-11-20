"""Run one headless Claude Code or codex call and return what it produced."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

PASSAGE_SCHEMA = {
    "type": "object",
    "properties": {"passage": {"type": "string"}},
    "required": ["passage"],
}
CODEX_REVIEW_PROFILE = Path.home() / ".codex" / "review.config.toml"


@dataclass(frozen=True)
class ClaudeCall:
    prompt: str
    model: str
    effort: str
    tools: tuple[str, ...]
    readable_dirs: tuple[Path, ...]
    cwd: Path
    system_append: str | None = None
    new_session_id: str | None = None
    resume_session_id: str | None = None
    json_schema: dict | None = None


@dataclass(frozen=True)
class ClaudeResult:
    text: str
    structured: dict | None
    session_id: str
    cost_usd: float
    served_models: tuple[str, ...]
    read_files: tuple[Path, ...]


@dataclass(frozen=True)
class ClaudeSettings:
    claude_bin: str
    timeout_s: int
    max_budget_usd: float


def claude_command(call: ClaudeCall, settings: ClaudeSettings) -> list[str]:
    """Build a `claude -p` command isolated from the user's own configuration.

    `--safe-mode` drops CLAUDE.md, skills, hooks, plugins and MCP servers, so each pipeline sees
    only the files its prompt names. A resumed call forks the session, so a failed turn can be
    rerun from the same starting point.
    """
    if call.new_session_id and call.resume_session_id:
        raise ValueError("a call either starts a session or resumes one, not both")
    command = [
        settings.claude_bin,
        "-p",
        "--safe-mode",
        "--strict-mcp-config",
        "--permission-prompts",
        "none",
        "--output-format",
        "json",
        "--model",
        call.model,
        "--effort",
        call.effort,
        "--tools",
        ",".join(call.tools),
        "--max-budget-usd",
        str(settings.max_budget_usd),
    ]
    for readable_dir in call.readable_dirs:
        command += ["--add-dir", str(readable_dir)]
    if call.new_session_id:
        command += ["--session-id", call.new_session_id]
    if call.resume_session_id:
        command += ["--resume", call.resume_session_id, "--fork-session"]
    if call.system_append:
        command += ["--append-system-prompt", call.system_append]
    if call.json_schema:
        command += ["--json-schema", json.dumps(call.json_schema)]
    return command


def run_claude(call: ClaudeCall, settings: ClaudeSettings) -> ClaudeResult:
    completed = subprocess.run(
        claude_command(call, settings),
        input=call.prompt,
        cwd=call.cwd,
        capture_output=True,
        text=True,
        timeout=settings.timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"claude exited {completed.returncode}: {completed.stderr[-2000:]}")
    messages = json.loads(completed.stdout)
    final = messages[-1]
    if final["type"] != "result" or final["is_error"] or final["subtype"] != "success":
        raise RuntimeError(f"claude call failed: {json.dumps(final)[:2000]}")
    served_models = tuple(sorted(final["modelUsage"]))
    if not any(call.model in model_name for model_name in served_models):
        raise RuntimeError(f"asked for {call.model!r} but {served_models} served the call")
    structured = final.get("structured_output")
    if call.json_schema and structured is None:
        raise RuntimeError("claude returned no structured output for a call with a JSON schema")
    return ClaudeResult(
        text=final["result"],
        structured=structured,
        session_id=final["session_id"],
        cost_usd=final["total_cost_usd"],
        served_models=served_models,
        read_files=files_read(messages),
    )


def files_read(messages: list[dict]) -> tuple[Path, ...]:
    """Every file the call opened with the Read tool, with symlinks resolved."""
    return tuple(
        Path(item["input"]["file_path"]).resolve()
        for message in messages
        if message["type"] == "assistant"
        for item in message["message"]["content"]
        if item["type"] == "tool_use" and item["name"] == "Read"
    )


def run_codex(prompt: str, workdir: Path, output_file: Path, codex_bin: str, timeout_s: int) -> str:
    """Run `codex exec` read-only and return its final message.

    The `review` profile is what makes the run read-only; codex silently ignores a missing
    profile and runs write-capable, so its absence is an error here.
    """
    if not CODEX_REVIEW_PROFILE.is_file():
        raise FileNotFoundError(f"{CODEX_REVIEW_PROFILE} is missing; codex would run write-capable")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        codex_bin,
        "exec",
        "-p",
        "review",
        "-C",
        str(workdir),
        "--skip-git-repo-check",
        "-o",
        str(output_file),
        prompt,
    ]
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"codex exited {completed.returncode}: {completed.stderr[-2000:]}")
    if not output_file.is_file() or not output_file.read_text().strip():
        raise RuntimeError(f"codex wrote no final message to {output_file}")
    return output_file.read_text()
