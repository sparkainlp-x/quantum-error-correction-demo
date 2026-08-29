"""
OES-32 dual-source water wave simulator.

This module models classical wave interference from two sources
on a circular water surface or membrane, then converts the surface
amplitude into a normalized intensity-like probability distribution
across N spatial states.

This is a classical wave visualization. Squaring surface amplitude
mirrors classical wave intensity and is only mathematically analogous
to the quantum Born rule. This code does not model or claim quantum
entanglement, consciousness effects, or biological healing.
"""

from __future__ import annotations

import numpy as np


def dual_source_water_state(
    time: float,
    N: int = 100,
    f_left: float = 80.0,
    f_right: float = 84.0,
    source_ratio: float = 1.0,
    noise_values: np.ndarray | None = None,
    noise: float = 0.02,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute a dual-source wave field and its normalized intensity.

    Parameters
    ----------
    time : float
        Simulation time in seconds.
    N : int
        Number of spatial states around the membrane, N > 1.
    f_left : float
        Frequency of the left source in Hz.
    f_right : float
        Frequency of the right source in Hz.
    source_ratio : float
        Relative amplitude of the right source.
    noise_values : np.ndarray or None
        Optional externally generated noise, shape (N,).
        Supply smoothed/correlated noise for stable animation.
    noise : float
        Noise amplitude scaling factor.

    Returns
    -------
    surface : np.ndarray, shape (N,)
        Combined wave amplitude at each spatial state.
    probabilities : np.ndarray, shape (N,)
        Normalized intensity distribution, sums to 1.
    """
    if not isinstance(N, int) or N <= 1:
        raise ValueError("N must be an integer greater than 1")

    angles = 2 * np.pi * np.arange(N) / N

    source_left = np.sin(
        2 * np.pi * f_left * time + 3 * angles
    )

    source_right = source_ratio * np.sin(
        2 * np.pi * f_right * time - 2 * angles + 0.7
    )

    surface = source_left + source_right

    if noise_values is not None:
        surface = surface + noise * noise_values

    intensity = surface ** 2
    total_intensity = np.sum(intensity)

    if total_intensity > 1e-12:
        probabilities = intensity / total_intensity
    else:
        probabilities = np.ones(N) / N

    return surface, probabilities
