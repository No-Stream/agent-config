from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from PIL import Image

import vizstyle
from vizstyle import DARK, LIGHT, Theme


def draw_simple_line_plot(theme: Theme) -> Figure:
    fig, ax = plt.subplots(figsize=(4, 3))
    steps = pd.Series(np.arange(10))
    ax.plot(steps, steps**2, label="series")
    ax.set_xlabel("Step")
    ax.set_ylabel("Value")
    ax.set_title("Value by step")
    vizstyle.add_caption(fig, "Pale caption below the plot.", theme)
    return fig


class TestSaveFigure:
    def test_writes_one_png_per_theme_with_theme_background(self, tmp_path: Path) -> None:
        saved_paths = vizstyle.save_figure(draw_simple_line_plot, tmp_path / "simple", themes=(LIGHT, DARK))

        assert [path.name for path in saved_paths] == ["simple_light.png", "simple_dark.png"]
        for path, theme in zip(saved_paths, (LIGHT, DARK)):
            corner_pixel = Image.open(path).convert("RGB").getpixel((2, 2))
            assert corner_pixel == tuple(int(theme.background[i : i + 2], 16) for i in (1, 3, 5))

    def test_theme_does_not_leak_into_later_figures(self, tmp_path: Path) -> None:
        default_facecolor = matplotlib.rcParams["figure.facecolor"]
        vizstyle.save_figure(draw_simple_line_plot, tmp_path / "simple", themes=(DARK,))
        assert matplotlib.rcParams["figure.facecolor"] == default_facecolor

    def test_closes_figures(self, tmp_path: Path) -> None:
        open_before = len(plt.get_fignums())
        vizstyle.save_figure(draw_simple_line_plot, tmp_path / "simple", themes=(LIGHT, DARK))
        assert len(plt.get_fignums()) == open_before

    def test_rejects_stem_with_suffix(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="suffix"):
            vizstyle.save_figure(draw_simple_line_plot, tmp_path / "simple.png", themes=(LIGHT,))


class TestThemeContext:
    def test_palette_drives_color_cycle(self) -> None:
        with vizstyle.theme_context(LIGHT):
            fig, ax = plt.subplots()
            first_line = ax.plot([0, 1], [0, 1])[0]
            assert matplotlib.colors.to_hex(first_line.get_color()) == LIGHT.palette[0]
            plt.close(fig)

    def test_palettes_have_cool_colors_first(self) -> None:
        for theme in (LIGHT, DARK):
            first_three_hues = [matplotlib.colors.rgb_to_hsv(matplotlib.colors.to_rgb(c))[0] * 360 for c in theme.palette[:3]]
            assert all(120 <= hue <= 290 for hue in first_three_hues), first_three_hues


class TestMarkBeyondLimit:
    def test_marks_only_values_beyond_limit_and_labels_them(self) -> None:
        with vizstyle.theme_context(LIGHT):
            fig, ax = plt.subplots()
            positions = pd.Series([0, 1, 2, 3])
            values = pd.Series([1.0, 2.0, 50.0, 3.0])
            ax.scatter(positions, values.clip(upper=5))
            ax.set_ylim(0, 5)
            n_marked = vizstyle.mark_beyond_limit(ax, positions, values, upper_limit=5, theme=LIGHT, axis="y")

            assert n_marked == 1
            assert [text.get_text() for text in ax.texts] == ["50"]
            assert ax.get_ylim() == (0, 5)
            plt.close(fig)

    def test_horizontal_axis(self) -> None:
        with vizstyle.theme_context(LIGHT):
            fig, ax = plt.subplots()
            positions = pd.Series([0, 1])
            values = pd.Series([4600.0, 90.0])
            ax.set_xlim(0, 300)
            n_marked = vizstyle.mark_beyond_limit(ax, positions, values, upper_limit=300, theme=LIGHT, axis="x")

            assert n_marked == 1
            assert [text.get_text() for text in ax.texts] == ["4.6k"]
            plt.close(fig)

    def test_merges_several_off_scale_values_at_one_position(self) -> None:
        with vizstyle.theme_context(LIGHT):
            fig, ax = plt.subplots()
            positions = pd.Series([0, 0, 0, 1])
            values = pd.Series([4200.0, 7600.0, 5100.0, 90.0])
            ax.set_xlim(0, 300)
            n_marked = vizstyle.mark_beyond_limit(ax, positions, values, upper_limit=300, theme=LIGHT, axis="x")

            assert n_marked == 3
            assert [text.get_text() for text in ax.texts] == ["3 up to 7.6k"]
            plt.close(fig)

    def test_rejects_misaligned_inputs(self) -> None:
        fig, ax = plt.subplots()
        with pytest.raises(ValueError, match="same length"):
            vizstyle.mark_beyond_limit(ax, pd.Series([0, 1]), pd.Series([1.0]), upper_limit=5, theme=LIGHT, axis="y")
        plt.close(fig)


class TestCaption:
    def test_rejects_more_than_three_sentences(self) -> None:
        fig, _ = plt.subplots()
        with pytest.raises(ValueError, match="three sentences"):
            vizstyle.add_caption(fig, "One. Two. Three. Four.", LIGHT)
        plt.close(fig)


class TestLabelLineEnds:
    def test_nudges_colliding_labels_apart_and_removes_legend(self) -> None:
        with vizstyle.theme_context(LIGHT):
            fig, ax = plt.subplots(figsize=(4, 3))
            steps = pd.Series(np.arange(10))
            ax.plot(steps, steps * 0 + 1.00, label="lr_1e-3")
            ax.plot(steps, steps * 0 + 1.01, label="lr_3e-4")
            ax.plot(steps, steps * 0 + 5.00, label="lr_3e-3")
            ax.legend()
            ax.set_ylim(0, 6)
            vizstyle.label_line_ends(ax, min_gap_points=11)

            vertical_offsets = sorted(text.xyann[1] for text in ax.texts)
            assert ax.get_legend() is None
            assert {text.get_text() for text in ax.texts} == {"lr_1e-3", "lr_3e-4", "lr_3e-3"}
            label_positions_points = sorted(
                ax.transData.transform(text.xy)[1] * 72 / fig.dpi + text.xyann[1] for text in ax.texts
            )
            gaps = np.diff(label_positions_points)
            assert (gaps >= 11 - 1e-6).all(), gaps
            assert vertical_offsets[0] == 0
            plt.close(fig)


class TestPlainLogTicks:
    def test_log_axis_ticks_are_plain_numbers(self) -> None:
        with vizstyle.theme_context(LIGHT):
            fig, ax = plt.subplots()
            ax.plot([5, 9000], [0, 1])
            ax.set_xscale("log")
            vizstyle.plain_log_ticks(ax, axis="x")
            fig.canvas.draw()
            tick_labels = [label.get_text() for label in ax.get_xticklabels() if label.get_text()]
            assert "10" in tick_labels and "1k" in tick_labels, tick_labels
            assert not any("$" in label for label in tick_labels), tick_labels
            plt.close(fig)

    def test_rejects_linear_axis(self) -> None:
        fig, ax = plt.subplots()
        with pytest.raises(ValueError, match="log"):
            vizstyle.plain_log_ticks(ax, axis="y")
        plt.close(fig)
