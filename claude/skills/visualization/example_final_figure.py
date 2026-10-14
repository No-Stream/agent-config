"""Worked example of a final figure: "our model beats each baseline", for a blog post (dark and light exports).

Run: python example_final_figure.py <output_dir>
"""

import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

import vizstyle
from vizstyle import DARK, LIGHT, Theme

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

REFERENCE_MODEL = "rl_tuned"
BOOTSTRAP_RESAMPLES = 10_000


def make_example_eval_results() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    true_accuracy = {"base": 0.61, "sft": 0.66, "dpo": 0.68, "rl_tuned": 0.74}
    rows = [
        dict(model=model, seed=seed, accuracy=rng.binomial(1000, accuracy + seed_effect) / 1000)
        for seed, seed_effect in enumerate(rng.normal(0, 0.01, 5))
        for model, accuracy in true_accuracy.items()
    ]
    return pd.DataFrame(rows)


def paired_difference_summary(eval_results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-baseline mean gain of the reference model with a 95% bootstrap CI (paired by seed), and the per-seed gains."""
    accuracy_by_seed = eval_results.pivot(index="seed", columns="model", values="accuracy")
    if accuracy_by_seed.isna().any().any():
        raise ValueError("Every model needs a score for every seed to pair the differences")
    gains = accuracy_by_seed.drop(columns=REFERENCE_MODEL).rsub(accuracy_by_seed[REFERENCE_MODEL], axis=0) * 100
    rng = np.random.default_rng(0)
    resampled_seed_rows = rng.integers(0, len(gains), size=(BOOTSTRAP_RESAMPLES, len(gains)))
    bootstrap_means = pd.DataFrame(
        {baseline: gains[baseline].to_numpy()[resampled_seed_rows].mean(axis=1) for baseline in gains.columns}
    )
    summary = pd.DataFrame(
        {
            "mean_gain": gains.mean(),
            "ci_low": bootstrap_means.quantile(0.025),
            "ci_high": bootstrap_means.quantile(0.975),
        }
    )
    return summary.sort_values("mean_gain"), gains


def main(output_dir: Path) -> None:
    eval_results = make_example_eval_results()
    summary, gains_by_seed = paired_difference_summary(eval_results)
    n_seeds = len(gains_by_seed)

    closest_baseline = summary.index[0]
    assert (summary["ci_low"] > 0).all(), f"Title claims a gain over every baseline:\n{summary}"
    title = (
        f"RL tuning beats every baseline, by at least "
        f"{summary.loc[closest_baseline, 'mean_gain']:.1f} points (vs {closest_baseline.upper()})"
    )

    def draw(theme: Theme) -> Figure:
        fig, ax = plt.subplots(figsize=(8, 2.8))
        positions = pd.Series(np.arange(len(summary)), index=summary.index)
        for baseline in summary.index:
            ax.scatter(
                gains_by_seed[baseline],
                np.full(n_seeds, positions[baseline]) + 0.18,
                s=12,
                color=theme.context_gray,
                zorder=2,
            )
        ax.errorbar(
            summary["mean_gain"],
            positions,
            xerr=[summary["mean_gain"] - summary["ci_low"], summary["ci_high"] - summary["mean_gain"]],
            fmt="o",
            markersize=8,
            capsize=0,
            elinewidth=2.5,
            color=theme.palette[0],
            zorder=3,
        )
        ax.axvline(0, color=theme.muted_ink, linewidth=1)
        ax.set_yticks(positions, [f"vs {baseline.upper()}" for baseline in summary.index])
        ax.set_xlim(left=min(-1, gains_by_seed.min().min() - 1))
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.set_xlabel("Accuracy gain of RL-tuned model (percentage points)")
        ax.set_title(title)
        vizstyle.add_caption(
            fig,
            f"Mean gain with 95% bootstrap CI over {n_seeds} seeds, paired by seed. Gray dots are individual seeds.",
            theme,
        )
        return fig

    saved_paths = vizstyle.save_figure(draw, output_dir / "rl_gain_over_baselines", themes=(DARK, LIGHT))
    logger.info("Saved %s", [str(path) for path in saved_paths])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
