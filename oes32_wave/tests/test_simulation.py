"""
Tests for oes32_wave/simulation.py — OES-32 dual-source wave simulator.

Run with:
    pytest oes32_wave/tests/test_simulation.py -v
"""

import numpy as np
import pytest

from oes32_wave.simulation import dual_source_water_state


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _call(**kwargs):
    """Call dual_source_water_state with defaults overridden by kwargs."""
    defaults = dict(time=0.0, N=100)
    defaults.update(kwargs)
    return dual_source_water_state(**defaults)


# ---------------------------------------------------------------------------
# input validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_N_must_be_int(self):
        with pytest.raises(ValueError, match="N must be an integer greater than 1"):
            dual_source_water_state(time=0.0, N=100.0)  # type: ignore[arg-type]

    def test_N_must_be_greater_than_1(self):
        with pytest.raises(ValueError, match="N must be an integer greater than 1"):
            dual_source_water_state(time=0.0, N=1)

    def test_N_zero_raises(self):
        with pytest.raises(ValueError):
            dual_source_water_state(time=0.0, N=0)

    def test_N_negative_raises(self):
        with pytest.raises(ValueError):
            dual_source_water_state(time=0.0, N=-5)

    def test_N_equals_2_is_valid(self):
        surface, probs = dual_source_water_state(time=0.0, N=2)
        assert len(surface) == 2
        assert len(probs) == 2


# ---------------------------------------------------------------------------
# output shapes
# ---------------------------------------------------------------------------

class TestOutputShapes:
    @pytest.mark.parametrize("N", [2, 10, 32, 100, 256])
    def test_surface_shape(self, N):
        surface, _ = _call(N=N)
        assert surface.shape == (N,)

    @pytest.mark.parametrize("N", [2, 10, 32, 100, 256])
    def test_probabilities_shape(self, N):
        _, probs = _call(N=N)
        assert probs.shape == (N,)

    def test_returns_tuple_of_two(self):
        result = _call()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# probabilities invariants
# ---------------------------------------------------------------------------

class TestProbabilitiesInvariants:
    def test_probabilities_sum_to_one(self):
        _, probs = _call(N=100, time=0.123)
        assert abs(probs.sum() - 1.0) < 1e-10

    @pytest.mark.parametrize("time", [0.0, 0.001, 0.01, 0.1, 1.0, 10.0])
    def test_probabilities_sum_to_one_various_times(self, time):
        _, probs = _call(N=64, time=time)
        assert abs(probs.sum() - 1.0) < 1e-10

    def test_probabilities_non_negative(self):
        _, probs = _call(N=100, time=0.5)
        assert np.all(probs >= 0.0)

    def test_probabilities_finite(self):
        _, probs = _call(N=100, time=0.5)
        assert np.all(np.isfinite(probs))


# ---------------------------------------------------------------------------
# near-zero intensity fallback
# ---------------------------------------------------------------------------

class TestNearZeroIntensity:
    def test_uniform_fallback_when_surface_all_zero(self):
        """
        Force total intensity ≈ 0 by choosing time and N so both sources cancel.
        As a unit test we can check the fallback branch directly by passing
        source_ratio=0 and f_left=0 so source_left=0 everywhere at t=0
        and ensuring source_right is also zero.
        """
        # At time=0, f_left=0: source_left = sin(0 + 3*angles) = sin(3*angles)
        # This is NOT zero generally, so we set noise to overwhelm and verify
        # the normal branch. For the near-zero branch we test it explicitly:
        # Construct a noise array that exactly cancels the deterministic part.
        N = 8
        time = 0.0
        f_left, f_right = 0.0, 0.0
        source_ratio = 0.0
        # With f_left=f_right=0 and source_ratio=0:
        # source_left = sin(3*angles), source_right = 0
        # Use source_ratio=0 and f_left=0 to get sin(3*angles)
        # Instead, call with noise=0 and check sum-to-one regardless:
        angles = 2 * np.pi * np.arange(N) / N
        cancel_noise = -np.sin(3 * angles)  # cancels source_left at t=0, f_left=0
        surface, probs = dual_source_water_state(
            time=0.0,
            N=N,
            f_left=0.0,
            f_right=0.0,
            source_ratio=0.0,
            noise_values=cancel_noise,
            noise=1.0,
        )
        # surface should be all-zero → uniform fallback
        assert np.allclose(surface, 0.0, atol=1e-12)
        assert np.allclose(probs, 1.0 / N, atol=1e-12)

    def test_near_zero_probs_sum_to_one(self):
        N = 8
        angles = 2 * np.pi * np.arange(N) / N
        cancel = -np.sin(3 * angles)
        _, probs = dual_source_water_state(
            time=0.0, N=N, f_left=0.0, f_right=0.0,
            source_ratio=0.0, noise_values=cancel, noise=1.0,
        )
        assert abs(probs.sum() - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# noise injection
# ---------------------------------------------------------------------------

class TestNoiseInjection:
    def test_no_noise_without_noise_values(self):
        """Without noise_values the result is fully deterministic."""
        s1, p1 = dual_source_water_state(time=0.5, N=32)
        s2, p2 = dual_source_water_state(time=0.5, N=32)
        assert np.array_equal(s1, s2)
        assert np.array_equal(p1, p2)

    def test_noise_values_affect_surface(self):
        N = 32
        noise_vals = np.ones(N)
        s_no_noise, _ = dual_source_water_state(time=0.5, N=N, noise=0.1)
        s_noise, _ = dual_source_water_state(
            time=0.5, N=N, noise=0.1, noise_values=noise_vals
        )
        assert not np.array_equal(s_no_noise, s_noise)

    def test_zero_noise_amplitude_ignores_noise_values(self):
        N = 32
        noise_vals = np.ones(N) * 999.0  # large but multiplied by noise=0
        s_base, _ = dual_source_water_state(time=0.5, N=N, noise=0.0)
        s_with, _ = dual_source_water_state(
            time=0.5, N=N, noise=0.0, noise_values=noise_vals
        )
        assert np.array_equal(s_base, s_with)

    def test_noise_values_shape_mismatch_raises(self):
        """Passing noise_values with wrong shape should raise."""
        with pytest.raises(Exception):
            dual_source_water_state(
                time=0.0, N=32, noise_values=np.ones(10), noise=0.1
            )


# ---------------------------------------------------------------------------
# source_ratio
# ---------------------------------------------------------------------------

class TestSourceRatio:
    def test_source_ratio_zero_removes_right_source(self):
        """With source_ratio=0, only the left source contributes."""
        s_ratio0, _ = dual_source_water_state(
            time=0.1, N=50, source_ratio=0.0, noise=0.0
        )
        angles = 2 * np.pi * np.arange(50) / 50
        expected = np.sin(2 * np.pi * 80.0 * 0.1 + 3 * angles)
        assert np.allclose(s_ratio0, expected, atol=1e-12)

    def test_source_ratio_two_doubles_right(self):
        s1, _ = dual_source_water_state(
            time=0.1, N=50, source_ratio=1.0, noise=0.0
        )
        s2, _ = dual_source_water_state(
            time=0.1, N=50, source_ratio=2.0, noise=0.0
        )
        assert not np.array_equal(s1, s2)


# ---------------------------------------------------------------------------
# time evolution
# ---------------------------------------------------------------------------

class TestTimeEvolution:
    def test_different_times_give_different_surfaces(self):
        s0, _ = dual_source_water_state(time=0.0, N=64)
        s1, _ = dual_source_water_state(time=0.001, N=64)
        assert not np.array_equal(s0, s1)

    def test_surface_values_finite_at_large_time(self):
        surface, probs = dual_source_water_state(time=1e6, N=64)
        assert np.all(np.isfinite(surface))
        assert np.all(np.isfinite(probs))
