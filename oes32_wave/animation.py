"""
animation.py — Matplotlib animation for the OES-32 dual-source wave simulator.

Displays two subplots side-by-side:
  Left  — surface amplitude around the circular membrane.
  Right — normalized intensity distribution (classical wave probability).

Noise is generated once per frame using an AR(1) process so it remains
temporally smooth across frames rather than being independent each frame.

Usage
-----
    python3 animation.py [--N 100] [--fps 30] [--duration 10]
                         [--f-left 80] [--f-right 84]
                         [--noise 0.02] [--ar-coeff 0.95]
                         [--source-ratio 1.0]
"""

from __future__ import annotations

import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend; switch to "TkAgg" for a window
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from simulation import dual_source_water_state


# ---------------------------------------------------------------------------
# smooth noise generator
# ---------------------------------------------------------------------------

class AR1NoiseGenerator:
    """
    Temporally-smooth AR(1) noise: x[t] = coeff * x[t-1] + sqrt(1-coeff²) * w
    where w ~ N(0,1).  The marginal distribution is N(0,1) at every step.
    """

    def __init__(self, N: int, coeff: float = 0.95, seed: int = 0) -> None:
        if not 0.0 <= coeff < 1.0:
            raise ValueError("AR(1) coefficient must be in [0, 1)")
        self._coeff = coeff
        self._innov_std = np.sqrt(1.0 - coeff ** 2)
        self._rng = np.random.default_rng(seed)
        self._state = self._rng.standard_normal(N)

    def next(self) -> np.ndarray:
        """Advance one step and return the current noise vector."""
        innovation = self._rng.standard_normal(len(self._state))
        self._state = self._coeff * self._state + self._innov_std * innovation
        return self._state.copy()


# ---------------------------------------------------------------------------
# animator
# ---------------------------------------------------------------------------

class WaveAnimator:
    """Builds and runs the Matplotlib animation."""

    def __init__(
        self,
        N: int = 100,
        fps: int = 30,
        duration: float = 10.0,
        f_left: float = 80.0,
        f_right: float = 84.0,
        noise_amp: float = 0.02,
        ar_coeff: float = 0.95,
        source_ratio: float = 1.0,
    ) -> None:
        self.N = N
        self.fps = fps
        self.n_frames = int(duration * fps)
        self.dt = 1.0 / fps
        self.f_left = f_left
        self.f_right = f_right
        self.noise_amp = noise_amp
        self.source_ratio = source_ratio

        self._noise_gen = AR1NoiseGenerator(N, coeff=ar_coeff)
        self._angles = np.linspace(0, 2 * np.pi, N, endpoint=False)
        self._time = 0.0

        self._build_figure()

    def _build_figure(self) -> None:
        self.fig, (self.ax_surf, self.ax_prob) = plt.subplots(
            1, 2, figsize=(12, 4)
        )

        # --- surface amplitude ---
        (self.line_surf,) = self.ax_surf.plot(
            np.degrees(self._angles),
            np.zeros(self.N),
            color="steelblue",
            linewidth=1.5,
        )
        self.ax_surf.set_xlim(0, 360)
        self.ax_surf.set_ylim(-2.5, 2.5)
        self.ax_surf.set_xlabel("Angle (°)")
        self.ax_surf.set_ylabel("Amplitude")
        self.ax_surf.set_title("Surface amplitude — dual-source wave")
        self.ax_surf.axhline(0, color="gray", linewidth=0.5, linestyle="--")

        # --- intensity distribution ---
        x = np.arange(self.N)
        self.bar_prob = self.ax_prob.bar(
            x,
            np.ones(self.N) / self.N,
            color="coral",
            width=1.0,
            align="edge",
        )
        self.ax_prob.set_xlim(0, self.N)
        self.ax_prob.set_ylim(0, 0.05)
        self.ax_prob.set_xlabel("Spatial state index")
        self.ax_prob.set_ylabel("Normalized intensity")
        self.ax_prob.set_title("Intensity distribution (classical)")

        self.time_text = self.fig.text(
            0.5, 0.01,
            "t = 0.000 s",
            ha="center",
            fontsize=9,
            color="dimgray",
        )

        self.fig.tight_layout(rect=[0, 0.04, 1, 1])

    def _update(self, frame: int):
        noise_vals = self._noise_gen.next()
        surface, probs = dual_source_water_state(
            time=self._time,
            N=self.N,
            f_left=self.f_left,
            f_right=self.f_right,
            source_ratio=self.source_ratio,
            noise_values=noise_vals,
            noise=self.noise_amp,
        )

        # update surface line
        self.line_surf.set_ydata(surface)

        # update bar heights
        prob_max = probs.max()
        if prob_max > 0:
            self.ax_prob.set_ylim(0, max(0.05, prob_max * 1.15))
        for bar, h in zip(self.bar_prob, probs):
            bar.set_height(h)

        self.time_text.set_text(f"t = {self._time:.3f} s")
        self._time += self.dt

        return (self.line_surf, *self.bar_prob, self.time_text)

    def build(self) -> animation.FuncAnimation:
        return animation.FuncAnimation(
            self.fig,
            self._update,
            frames=self.n_frames,
            interval=1000 // self.fps,
            blit=True,
        )

    def save(self, path: str, writer: str = "pillow") -> None:
        anim = self.build()
        anim.save(path, writer=writer, fps=self.fps)
        print(f"Animation saved to {path}")

    def show(self) -> None:
        matplotlib.use("TkAgg")
        anim = self.build()  # noqa: F841 — keep reference alive
        plt.show()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="OES-32 dual-source wave animation"
    )
    p.add_argument("--N", type=int, default=100,
                   help="Number of spatial states [default: 100]")
    p.add_argument("--fps", type=int, default=30,
                   help="Frames per second [default: 30]")
    p.add_argument("--duration", type=float, default=10.0,
                   help="Animation duration in seconds [default: 10]")
    p.add_argument("--f-left", type=float, default=80.0,
                   help="Left source frequency Hz [default: 80]")
    p.add_argument("--f-right", type=float, default=84.0,
                   help="Right source frequency Hz [default: 84]")
    p.add_argument("--noise", type=float, default=0.02,
                   help="Noise amplitude [default: 0.02]")
    p.add_argument("--ar-coeff", type=float, default=0.95,
                   help="AR(1) noise temporal smoothness [default: 0.95]")
    p.add_argument("--source-ratio", type=float, default=1.0,
                   help="Right/left source amplitude ratio [default: 1.0]")
    p.add_argument("--output", type=str, default=None,
                   help="Save animation to this file (e.g. wave.gif)")
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)
    animator = WaveAnimator(
        N=args.N,
        fps=args.fps,
        duration=args.duration,
        f_left=args.f_left,
        f_right=args.f_right,
        noise_amp=args.noise,
        ar_coeff=args.ar_coeff,
        source_ratio=args.source_ratio,
    )
    if args.output:
        animator.save(args.output)
    else:
        animator.show()


if __name__ == "__main__":
    main()
