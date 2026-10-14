#!/usr/bin/python3
"""Codex PreToolUse guard: hard-blocks destructive commands when Codex runs without a sandbox.

Codex's prefix rules (~/.codex/rules/default.rules) only see argv prefixes and match a whole
`bash -lc` script as one unit once it uses redirection, `$VAR`, globs or substitutions, so
`git -C repo push` or `git push > log` slips past them. This hook re-checks every shell call:

1. the regex classes from the Claude Code guard (~/.claude/hooks/guard-bash.sh: curl|bash,
   credential reads, sudo/dd/mkfs, destructive AWS, ...) by running that script unchanged;
2. the Claude Code permissions.deny list and the owner's git policy, on each simple command
   after splitting on shell operators and skipping git's global options.

Runs under the system Python (3.8). Denial uses the PreToolUse JSON shape Codex shares with
Claude Code. Fails closed: a crash exits 2, which Codex treats as a block.
"""
import json
import os
import re
import shlex
import subprocess
import sys

CLAUDE_GUARD = os.path.expanduser("~/.claude/hooks/guard-bash.sh")

SEGMENT_SEPARATOR = re.compile(r"\|\||&&|[;|&\n`]|\$\(|<\(|>\(|[(){}]")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
COMMAND_WRAPPERS = {"command", "exec", "nohup", "time", "nice", "stdbuf", "xargs", "timeout", "env", "builtin"}
SHELLS = {"bash", "sh", "zsh", "dash"}
GIT_GLOBAL_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
PROTECTED_EDIT_PATH = re.compile(r"(^|/)\.(ssh|aws)/")


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason + " Ask the owner to run it manually if it is really needed.",
        }
    }))
    sys.exit(0)


def tokenize(segment: str) -> list:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        # Splitting on operators can cut through a quoted `bash -c '...'` script; drop the stray quotes.
        return segment.replace('"', " ").replace("'", " ").split()


def strip_prefixes(tokens: list) -> list:
    """Drop leading `FOO=bar` assignments and wrappers such as `env`, `nohup`, `timeout 5`."""
    while tokens:
        head = os.path.basename(tokens[0])
        if ENV_ASSIGNMENT.match(tokens[0]):
            tokens = tokens[1:]
        elif head in COMMAND_WRAPPERS:
            tokens = tokens[1:]
            while tokens and (tokens[0].startswith("-") or re.match(r"^\d+[smhd]?$", tokens[0])):
                tokens = tokens[1:]
        else:
            break
    return tokens


def short_flag_cluster_has(token: str, letter: str) -> bool:
    return bool(re.match(r"^-[A-Za-z]+$", token)) and letter in token


def git_subcommand(tokens: list) -> tuple:
    index = 1
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        index += 2 if option in GIT_GLOBAL_OPTIONS_WITH_VALUE else 1
    if index >= len(tokens):
        return "", []
    return tokens[index], tokens[index + 1:]


def git_violation(arguments_after_git: list) -> str:
    subcommand, args = git_subcommand(["git"] + arguments_after_git)
    if subcommand == "push":
        if any(
            a.startswith("--force")
            or a in ("--delete", "--mirror", "--prune", "--no-verify")
            or a.startswith("--delete=")
            or short_flag_cluster_has(a, "f")
            or short_flag_cluster_has(a, "d")
            or a.startswith("+")
            or (a.startswith(":") and len(a) > 1)
            for a in args
        ):
            return "Force pushes, remote deletions, and skipping push hooks are blocked."
    if subcommand in ("rebase", "filter-branch", "filter-repo"):
        return "git %s rewrites history and is blocked." % subcommand
    if subcommand == "pull" and any(a in ("--rebase", "-r") or a.startswith("--rebase=") for a in args):
        return "git pull --rebase is blocked."
    if subcommand == "reset" and any(a in ("--hard", "--merge", "--keep") for a in args):
        return "git reset --hard/--merge/--keep discards work and is blocked."
    if subcommand == "restore":
        return "git restore can discard uncommitted changes and is blocked; use git stash."
    if subcommand == "checkout" and any(a in ("--", ".", "-f", "--force") for a in args):
        return "git checkout -- <path> / . / --force discards uncommitted changes and is blocked; use git stash."
    if subcommand == "switch" and any(a in ("-f", "--force", "--discard-changes") for a in args):
        return "git switch --force/--discard-changes is blocked."
    if subcommand == "clean" and not any(a in ("-n", "--dry-run") for a in args):
        return "git clean deletes untracked files and is blocked (git clean -n is allowed)."
    if subcommand == "commit":
        if any(a in ("--amend", "--no-verify", "--no-gpg-sign") for a in args):
            return "git commit --amend/--no-verify/--no-gpg-sign is blocked."
        for arg in args:
            if arg == "--":
                break
            value_flag_position = re.search(r"[mFCct]", arg) if re.match(r"^-[A-Za-z]+$", arg) else None
            cluster = arg[: value_flag_position.start()] if value_flag_position else arg
            if short_flag_cluster_has(cluster, "n"):
                return "git commit -n (--no-verify) is blocked."
    if subcommand == "stash" and args[:1] and args[0] in ("drop", "clear"):
        return "git stash drop/clear is blocked."
    if subcommand == "branch" and any(
        a in ("--delete", "--move", "--copy", "--force") or (re.match(r"^-[A-Za-z]+$", a) and re.search(r"[dDmMcCf]", a))
        for a in args
    ):
        return "git branch delete/move/copy/force is blocked."
    if subcommand == "reflog" and args[:1] and args[0] in ("expire", "delete"):
        return "git reflog expire/delete is blocked."
    if subcommand == "tag" and args and not all(a in ("-l", "--list", "-n") or a.startswith("--list") for a in args):
        return "Creating or deleting git tags is blocked (git tag / git tag -l are allowed)."
    if subcommand == "update-ref" and "-d" in args:
        return "git update-ref -d is blocked."
    return ""


def simple_command_violation(tokens: list, depth: int) -> str:
    tokens = strip_prefixes(tokens)
    if not tokens:
        return ""
    program = os.path.basename(tokens[0])
    args = tokens[1:]
    if program in SHELLS:
        for index, arg in enumerate(args[:-1]):
            if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", arg):
                return script_violation(args[index + 1], depth + 1)
        return ""
    if program == "git":
        return git_violation(args)
    if program == "rm" and any(
        a in ("--recursive",) or (re.match(r"^-[A-Za-z]+$", a) and re.search(r"[rR]", a)) for a in args
    ):
        return "Recursive rm is blocked."
    if program == "mv":
        return "mv is blocked by the global policy (git mv is allowed)."
    if program in ("pip", "pip3") and args[:1] == ["install"]:
        return "pip install is blocked: add the dependency to pyproject.toml and use uv."
    if re.match(r"^python[0-9.]*$", program) and args[:3] == ["-m", "pip", "install"]:
        return "pip install is blocked: add the dependency to pyproject.toml and use uv."
    if program == "uv" and args[:2] == ["pip", "install"]:
        return "uv pip install is blocked: add the dependency to pyproject.toml and use uv sync."
    return ""


def script_violation(script: str, depth: int = 0) -> str:
    if depth > 4:
        return "Shell nesting too deep to check."
    for segment in SEGMENT_SEPARATOR.split(script):
        reason = simple_command_violation(tokenize(segment), depth)
        if reason:
            return reason
    return ""


def claude_guard_reason(event: dict) -> str:
    result = subprocess.run(
        ["bash", CLAUDE_GUARD], input=json.dumps(event), capture_output=True, text=True, check=True, timeout=20
    )
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def edit_paths(tool_input) -> list:
    text = json.dumps(tool_input)
    paths = re.findall(r"\*\*\* (?:Add|Update|Delete) File: ([^\\\n\"]+)", text)
    paths += re.findall(r"\*\*\* Move to: ([^\\\n\"]+)", text)
    if isinstance(tool_input, dict) and isinstance(tool_input.get("file_path"), str):
        paths.append(tool_input["file_path"])
    return paths


def main() -> None:
    event = json.load(sys.stdin)
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if isinstance(command, list):
            command = " ".join(shlex.quote(part) for part in command)
        reason = claude_guard_reason({"tool_input": {"command": command}}) or script_violation(command)
        if reason:
            deny(reason)
    elif tool_name in ("apply_patch", "Edit", "Write"):
        for path in edit_paths(tool_input):
            if PROTECTED_EDIT_PATH.search(path.strip()):
                deny("Editing files under ~/.ssh or ~/.aws is blocked.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as error:  # fail closed: any crash blocks the call
        sys.stderr.write("guard_shell.py failed, blocking the call: %r\n" % (error,))
        sys.exit(2)
