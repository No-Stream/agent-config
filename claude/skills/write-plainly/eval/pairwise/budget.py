"""What a run will call before it starts, and what it spent after."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pipeline_config import AgentStage, AuthorStage, Config, DraftStage, FidelityGate, LintLoop


def call_bounds(config: Config) -> dict[str, dict[str, tuple[int, int]]]:
    """Fewest and most fresh agents and author turns each pipeline starts per task."""
    bounds = {}
    for pipeline in config.pipelines:
        fresh = [0, 0]
        turns = [0, 0]
        for stage in pipeline.stages:
            match stage:
                case DraftStage(from_pipeline=None) | AgentStage():
                    fresh = [fresh[0] + 1, fresh[1] + 1]
                case DraftStage():  # copied from another pipeline, so no call
                    pass
                case AuthorStage(loop=None):
                    turns = [turns[0] + 1, turns[1] + 1]
                case AuthorStage(loop=LintLoop(max_rounds=max_rounds)):
                    turns = [turns[0] + 1, turns[1] + max_rounds]
                case FidelityGate():
                    fresh[1] += 1
                    turns[1] += 1
        bounds[pipeline.name] = {"fresh_agents": tuple(fresh), "author_turns": tuple(turns)}
    return bounds


def format_plan(config: Config, task_count: int) -> str:
    bounds = call_bounds(config)
    rows = ["| Pipeline | Fresh agents per task | Author turns per task |", "|---|---|---|"]
    for name, counts in bounds.items():
        fresh_low, fresh_high = counts["fresh_agents"]
        turns_low, turns_high = counts["author_turns"]
        rows.append(f"| {name} | {fresh_low} to {fresh_high} | {turns_low} to {turns_high} |")
    rows.append("| fidelity measurement | 1 | 0 |")
    fresh_low = sum(counts["fresh_agents"][0] for counts in bounds.values()) + 1
    fresh_high = sum(counts["fresh_agents"][1] for counts in bounds.values()) + 1
    turns_low = sum(counts["author_turns"][0] for counts in bounds.values())
    turns_high = sum(counts["author_turns"][1] for counts in bounds.values())
    rows.append(
        f"| **all, {task_count} tasks** | {fresh_low * task_count} to {fresh_high * task_count} "
        f"| {turns_low * task_count} to {turns_high * task_count} |"
    )
    return "\n".join(rows)


def cost_summary(out_dir: Path) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for stage_file in out_dir.glob("*/*/*.json"):
        record = json.loads(stage_file.read_text())
        if "copied_from" in record:
            continue
        totals[stage_file.parent.name] += sum(call["cost_usd"] for call in record["calls"])
    for fidelity_file in out_dir.glob("*/fidelity.json"):
        totals["fidelity measurement"] += json.loads(fidelity_file.read_text())["calls"][0][
            "cost_usd"
        ]
    return dict(totals)
