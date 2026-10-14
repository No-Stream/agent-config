"""Plot style for analysis and research figures: light and dark themes, a cool colorblind-checked palette, and helpers.

Copy this file into the project next to the plotting code rather than importing it from the skill directory.
"""

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from cycler import cycler
from matplotlib import ticker
from matplotlib.axes import Axes
from matplotlib.figure import Figure


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    ink: str
    muted_ink: str
    grid: str
    context_gray: str
    palette: tuple[str, ...]


# Both palettes were checked with the dataviz skill's validate_palette.js over all pairs (CVD and normal-vision
# separation, contrast). Blue, green and purple come first; amber and plum are only for a 4th and 5th category.
# The dark purple is lighter than that validator's UI lightness band on purpose: a darker purple cannot be told
# apart from the blue under protanopia.
LIGHT = Theme(
    name="light",
    background="#ffffff",
    ink="#1d2026",
    muted_ink="#6b7280",
    grid="#e6e8eb",
    context_gray="#b4b9c2",
    palette=("#1f5fbf", "#2a9d6f", "#a47de3", "#c47812", "#8c3672"),
)
DARK = Theme(
    name="dark",
    background="#15171c",
    ink="#e8eaee",
    muted_ink="#9aa1ac",
    grid="#2a2e36",
    context_gray="#5c626d",
    palette=("#3068c8", "#30a272", "#ab8cee", "#c9832a", "#b9478a"),
)


def theme_rc_params(theme: Theme) -> dict[str, Any]:
    return {
        "figure.facecolor": theme.background,
        "axes.facecolor": theme.background,
        "savefig.facecolor": theme.background,
        "savefig.edgecolor": theme.background,
        "text.color": theme.ink,
        "axes.labelcolor": theme.ink,
        "axes.titlecolor": theme.ink,
        "axes.edgecolor": theme.muted_ink,
        "xtick.color": theme.muted_ink,
        "ytick.color": theme.muted_ink,
        "grid.color": theme.grid,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": cycler(color=list(theme.palette)),
        "axes.titlelocation": "left",
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "font.size": 11,
        "legend.frameon": False,
        "lines.linewidth": 2,
        "figure.constrained_layout.use": True,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    }


@contextmanager
def theme_context(theme: Theme) -> Iterator[None]:
    with mpl.rc_context(theme_rc_params(theme)):
        yield


def save_figure(
    draw: Callable[[Theme], Figure], path_stem: Path, themes: tuple[Theme, ...], suffix: str = ".png"
) -> list[Path]:
    """Render `draw(theme)` once per theme and save each as `<path_stem>_<theme name><suffix>`.

    Pass `themes=(LIGHT,)` for papers, `(DARK, LIGHT)` for blog posts.
    """
    if path_stem.suffix:
        raise ValueError(f"path_stem must have no suffix, got {path_stem}; the theme name and suffix are appended")
    saved_paths = []
    for theme in themes:
        with theme_context(theme):
            fig = draw(theme)
            path = path_stem.with_name(f"{path_stem.name}_{theme.name}{suffix}")
            fig.savefig(path)
            plt.close(fig)
        saved_paths.append(path)
    return saved_paths


def add_caption(fig: Figure, text: str, theme: Theme) -> None:
    """Pale gray explanatory text below the plot, at most three sentences."""
    sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", text.strip()) if sentence]
    if len(sentences) > 3:
        raise ValueError(f"Caption has {len(sentences)} sentences; keep it to three sentences or fewer")
    fig.text(0.0, -0.01, text, ha="left", va="top", fontsize=9, color=theme.muted_ink, wrap=True)


def format_compact(value: float) -> str:
    for threshold, unit_suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= threshold:
            return f"{value / threshold:.3g}{unit_suffix}"
    return f"{value:.3g}"


def plain_log_ticks(ax: Axes, axis: Literal["x", "y"]) -> None:
    """Label a log axis with plain numbers at 1-2-5 steps (10, 20, 50, 100, 1k) instead of powers of ten."""
    target_axis = ax.xaxis if axis == "x" else ax.yaxis
    if target_axis.get_scale() != "log":
        raise ValueError(f"The {axis} axis is not log scale; call ax.set_{axis}scale('log') first")
    target_axis.set_major_locator(ticker.LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    target_axis.set_major_formatter(ticker.FuncFormatter(lambda value, _position: format_compact(value)))
    target_axis.set_minor_formatter(ticker.NullFormatter())


def mark_beyond_limit(
    ax: Axes,
    positions: pd.Series,
    values: pd.Series,
    upper_limit: float,
    theme: Theme,
    axis: Literal["x", "y"],
) -> int:
    """Mark values above `upper_limit` with an arrowhead at the axis edge and their value. Returns the count marked.

    Several off-scale values at one position share a single marker labelled with their count and maximum.
    `axis` is the value axis. Plot the in-range data yourself and set the axis limit before calling this.
    Prefer a log scale for heavy-tailed data; use this when the range is still too large after that.
    """
    if len(positions) != len(values):
        raise ValueError(f"positions and values must have the same length, got {len(positions)} and {len(values)}")
    original_xlim, original_ylim = ax.get_xlim(), ax.get_ylim()
    beyond_limit = values.to_numpy() > upper_limit
    off_scale_by_position = (
        pd.DataFrame({"position": positions.to_numpy()[beyond_limit], "value": values.to_numpy()[beyond_limit]})
        .groupby("position", sort=False)["value"]
        .agg(["count", "max"])
    )
    for position, n_off_scale, max_value in off_scale_by_position.itertuples():
        label = format_compact(max_value) if n_off_scale == 1 else f"{n_off_scale} up to {format_compact(max_value)}"
        if axis == "y":
            marker_xy, marker, text_offset, alignment = (position, upper_limit), "^", (0, 7), dict(ha="center", va="bottom")
        else:
            marker_xy, marker, text_offset, alignment = (upper_limit, position), ">", (7, 0), dict(ha="left", va="center")
        ax.plot(*marker_xy, marker=marker, markersize=7, color=theme.ink, clip_on=False, zorder=5)
        ax.annotate(
            label,
            xy=marker_xy,
            xytext=text_offset,
            textcoords="offset points",
            fontsize=9,
            color=theme.muted_ink,
            annotation_clip=False,
            **alignment,
        )
    ax.set_xlim(original_xlim)
    ax.set_ylim(original_ylim)
    return int(beyond_limit.sum())


def label_line_ends(ax: Axes, min_gap_points: float = 11) -> None:
    """Replace the legend with labels at the right end of each labelled line, nudged apart so they do not collide.

    Call after setting the axis limits.
    """
    labelled_lines = [line for line in ax.get_lines() if not line.get_label().startswith("_")]
    if not labelled_lines:
        raise ValueError("No labelled lines on this axis; pass label=... when plotting")
    points_per_pixel = 72 / ax.figure.dpi
    line_ends = []
    for line in labelled_lines:
        line_data = pd.DataFrame({"x": line.get_xdata(), "y": line.get_ydata()}).dropna()
        end_x, end_y = line_data["x"].iloc[-1], line_data["y"].iloc[-1]
        end_y_points = ax.transData.transform((end_x, end_y))[1] * points_per_pixel
        line_ends.append((end_y_points, end_x, end_y, line))
    line_ends.sort(key=lambda line_end: line_end[0])

    previous_label_y_points = float("-inf")
    for end_y_points, end_x, end_y, line in line_ends:
        label_y_points = max(end_y_points, previous_label_y_points + min_gap_points)
        ax.annotate(
            line.get_label(),
            xy=(end_x, end_y),
            xytext=(6, label_y_points - end_y_points),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=10,
            color=line.get_color(),
            annotation_clip=False,
        )
        previous_label_y_points = label_y_points
    if ax.get_legend() is not None:
        ax.get_legend().remove()
