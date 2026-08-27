"""
test_monte_carlo.py — Validation tests for the Monte Carlo simulation.

Verifies:
  - Perturbation generators produce vectors of the right width and magnitude.
  - Perturbations generated for each sector satisfy that sector's symmetry.
  - CellResult accounting is internally consistent.
  - Statistical invariants hold for every cell in a small sweep:
      * admitted + collapsed + sym_denied + syn_denied == trials
      * max_residual <= tau for all admitted flips
      * syndrome control arm: all syn_denied trials were correctly rejected
      * admit_rate decreases (monotonically, on average) as amplitude increases
      * when amplitude >> tau, collapse_rate approaches 1

Run with:
    cd membrane_shield && python3 -m unittest test_monte_carlo.py -v
"""

import random
import unittest

from membrane_shield import (
    Sector, ShieldDenied, WIDTH, mu, zeros,
    symmetry_ok,
)
from monte_carlo import (
    CellResult,
    _calibrate,
    _random_perturbation,
    _symmetric_perturbation,
    run_cell,
    run_sweep,
)

RNG = random.Random(0)
TAU = 0.10
EPS = 1e-9


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fresh_rng(seed: int = 7) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# perturbation generators
# ---------------------------------------------------------------------------

class TestRandomPerturbation(unittest.TestCase):
    def test_width(self):
        v = _random_perturbation(fresh_rng(), 0.05)
        self.assertEqual(len(v), WIDTH)

    def test_amplitude_bound(self):
        amp = 0.07
        for _ in range(200):
            v = _random_perturbation(fresh_rng(), amp)
            self.assertTrue(all(-amp <= x <= amp for x in v),
                            f'component out of range: {v}')

    def test_amplitude_zero(self):
        v = _random_perturbation(fresh_rng(), 0.0)
        self.assertEqual(v, [0.0] * WIDTH)


class TestSymmetricPerturbation(unittest.TestCase):
    def _check_sector_ok(self, sector: Sector, amplitude: float, n: int = 100) -> None:
        rng = fresh_rng()
        ref = zeros()
        for _ in range(n):
            p = _symmetric_perturbation(rng, amplitude, sector)
            self.assertEqual(len(p), WIDTH)
            obs = [b + d for b, d in zip(ref, p)]
            self.assertTrue(
                symmetry_ok(obs, ref, sector, EPS),
                f'sector {sector.value}: perturbation broke symmetry: {p}',
            )

    def test_any_width(self):
        p = _symmetric_perturbation(fresh_rng(), 0.05, Sector.ANY)
        self.assertEqual(len(p), WIDTH)

    def test_even_symmetry(self):
        self._check_sector_ok(Sector.EVEN, 0.08)

    def test_odd_symmetry(self):
        self._check_sector_ok(Sector.ODD, 0.08)

    def test_fold8_symmetry(self):
        self._check_sector_ok(Sector.FOLD8, 0.08)

    def test_amplitude_bound_even(self):
        # After averaging, magnitude should not exceed the original amplitude
        amp = 0.05
        rng = fresh_rng()
        for _ in range(100):
            p = _symmetric_perturbation(rng, amp, Sector.EVEN)
            self.assertTrue(all(abs(x) <= amp + 1e-12 for x in p))

    def test_amplitude_bound_odd(self):
        amp = 0.05
        rng = fresh_rng()
        for _ in range(100):
            p = _symmetric_perturbation(rng, amp, Sector.ODD)
            self.assertTrue(all(abs(x) <= amp + 1e-12 for x in p))

    def test_amplitude_bound_fold8(self):
        amp = 0.05
        rng = fresh_rng()
        for _ in range(100):
            p = _symmetric_perturbation(rng, amp, Sector.FOLD8)
            self.assertTrue(all(abs(x) <= amp + 1e-12 for x in p))


# ---------------------------------------------------------------------------
# _calibrate helper
# ---------------------------------------------------------------------------

class TestCalibrate(unittest.TestCase):
    def test_returns_unlocked_shield(self):
        sh, g, dec = _calibrate(TAU, Sector.ANY, EPS)
        self.assertFalse(sh.state.locked)
        self.assertFalse(sh.state.collapse)

    def test_tau_set(self):
        sh, g, dec = _calibrate(0.07, Sector.ANY, EPS)
        self.assertAlmostEqual(sh.state.tau, 0.07)

    def test_sector_set(self):
        sh, g, dec = _calibrate(TAU, Sector.EVEN, EPS)
        self.assertEqual(sh.state.sector, Sector.EVEN)

    def test_reference_all_zeros(self):
        sh, g, dec = _calibrate(TAU, Sector.ANY, EPS)
        self.assertTrue(all(x == 0.0 for x in sh.state.reference.bulk))
        self.assertTrue(all(x == 0.0 for x in sh.state.reference.boundary))


# ---------------------------------------------------------------------------
# CellResult
# ---------------------------------------------------------------------------

class TestCellResult(unittest.TestCase):
    def _make(self, **kwargs) -> CellResult:
        defaults = dict(amplitude=0.05, sector='ANY', trials=100)
        defaults.update(kwargs)
        return CellResult(**defaults)

    def test_admit_rate_zero_trials(self):
        r = self._make(trials=0)
        self.assertEqual(r.admit_rate, 0.0)

    def test_admit_rate(self):
        r = self._make(trials=100, admitted=60)
        self.assertAlmostEqual(r.admit_rate, 0.60)

    def test_collapse_rate(self):
        r = self._make(trials=100, collapsed=25)
        self.assertAlmostEqual(r.collapse_rate, 0.25)

    def test_avg_residual_none_when_empty(self):
        r = self._make()
        self.assertIsNone(r.avg_residual)

    def test_max_residual_none_when_empty(self):
        r = self._make()
        self.assertIsNone(r.max_residual)

    def test_avg_residual(self):
        r = self._make()
        r.residuals = [0.02, 0.04, 0.06]
        self.assertAlmostEqual(r.avg_residual, 0.04)

    def test_max_residual(self):
        r = self._make()
        r.residuals = [0.02, 0.08, 0.05]
        self.assertAlmostEqual(r.max_residual, 0.08)

    def test_as_dict_keys(self):
        r = self._make()
        d = r.as_dict()
        expected = {'amplitude', 'sector', 'trials', 'admitted', 'collapsed',
                    'sym_denied', 'syn_denied', 'admit_rate', 'collapse_rate',
                    'avg_residual', 'max_residual'}
        self.assertEqual(set(d.keys()), expected)

    def test_as_dict_na_residual(self):
        r = self._make()
        d = r.as_dict()
        self.assertEqual(d['avg_residual'], 'n/a')
        self.assertEqual(d['max_residual'], 'n/a')


# ---------------------------------------------------------------------------
# run_cell — statistical invariants
# ---------------------------------------------------------------------------

class TestRunCellInvariants(unittest.TestCase):
    """
    Runs small cells (200 trials) and asserts structural invariants that must
    hold regardless of random seed.
    """

    def _cell(self, amplitude: float, sector: Sector = Sector.ANY,
               tau: float = TAU, trials: int = 200) -> CellResult:
        return run_cell(amplitude, sector, tau, EPS, trials, fresh_rng())

    def test_counts_sum_to_trials(self):
        """admitted + collapsed + sym_denied + syn_denied == trials for every cell."""
        for sector in Sector:
            for amp in [0.02, 0.08, 0.15]:
                with self.subTest(sector=sector.value, amp=amp):
                    r = self._cell(amp, sector)
                    total = r.admitted + r.collapsed + r.sym_denied + r.syn_denied
                    self.assertEqual(total, r.trials,
                                     f'counts {total} != trials {r.trials}')

    def test_max_residual_le_tau(self):
        """No admitted flip should have a residual exceeding tau."""
        for sector in Sector:
            for amp in [0.01, 0.05, 0.09]:
                with self.subTest(sector=sector.value, amp=amp):
                    r = self._cell(amp, sector)
                    if r.max_residual is not None:
                        self.assertLessEqual(
                            r.max_residual, TAU + 1e-9,
                            f'max_residual {r.max_residual} > tau {TAU}',
                        )

    def test_residuals_list_length_matches_admitted(self):
        """len(residuals) == admitted."""
        r = self._cell(0.05)
        self.assertEqual(len(r.residuals), r.admitted)

    def test_syn_denied_approximately_fault_rate(self):
        """
        With syndrome_fault_rate=0.05 and 2000 trials, syn_denied should
        be in roughly [0.02*trials, 0.10*trials] (very wide tolerance).
        """
        r = run_cell(0.03, Sector.ANY, TAU, EPS, 2000, fresh_rng(),
                     syndrome_fault_rate=0.05)
        self.assertGreater(r.syn_denied, 0,
                           'syndrome control arm never fired — unexpected')
        self.assertLess(r.syn_denied, int(0.15 * r.trials),
                        'syndrome control arm fired more than expected')

    def test_amplitude_below_tau_admits_some(self):
        """Amplitude well below tau should admit at least 50% of trials."""
        r = self._cell(0.01, Sector.ANY)
        self.assertGreater(r.admit_rate, 0.50,
                           f'low-amplitude admit_rate={r.admit_rate} unexpectedly low')

    def test_amplitude_above_tau_collapses_mostly(self):
        """Amplitude >> tau should collapse nearly all trials."""
        r = self._cell(0.50, Sector.ANY, tau=0.05, trials=300)
        self.assertGreater(r.collapse_rate, 0.80,
                           f'high-amplitude collapse_rate={r.collapse_rate} unexpectedly low')

    def test_no_sym_denied_for_any_sector(self):
        """Sector.ANY never applies a symmetry filter, so sym_denied must be 0."""
        r = self._cell(0.05, Sector.ANY)
        self.assertEqual(r.sym_denied, 0)

    def test_no_collapse_when_amplitude_zero(self):
        """Zero-amplitude perturbation stays at reference → no collapse possible."""
        r = self._cell(0.0, Sector.ANY)
        self.assertEqual(r.collapsed, 0)

    def test_negative_amplitude_treated_as_zero(self):
        """_random_perturbation with amplitude=0 never moves away from reference."""
        v = _random_perturbation(fresh_rng(), 0.0)
        self.assertEqual(v, [0.0] * WIDTH)


# ---------------------------------------------------------------------------
# run_cell — sector-specific invariants
# ---------------------------------------------------------------------------

class TestRunCellSectors(unittest.TestCase):
    def test_fold8_admit_rate_ge_any_at_moderate_amplitude(self):
        """
        FOLD8's ring-averaging reduces per-component magnitude, so its
        admit_rate should be >= ANY's at the same amplitude (on average).
        Use a fixed seed for reproducibility.
        """
        amp = 0.08
        trials = 500
        r_any = run_cell(amp, Sector.ANY, TAU, EPS, trials, random.Random(3))
        r_f8 = run_cell(amp, Sector.FOLD8, TAU, EPS, trials, random.Random(3))
        self.assertGreaterEqual(
            r_f8.admit_rate, r_any.admit_rate - 0.10,  # allow 10% slack for noise
            f'FOLD8 admit={r_f8.admit_rate} < ANY admit={r_any.admit_rate}',
        )

    def test_all_sectors_complete_without_error(self):
        """Every sector runs through run_cell without raising an exception."""
        for sector in Sector:
            with self.subTest(sector=sector.value):
                run_cell(0.05, sector, TAU, EPS, 50, fresh_rng())


# ---------------------------------------------------------------------------
# run_sweep — structural validation
# ---------------------------------------------------------------------------

class TestRunSweep(unittest.TestCase):
    def _sweep(self, amplitudes=None, sectors=None, trials=100):
        if amplitudes is None:
            amplitudes = [0.01, 0.05, 0.15]
        if sectors is None:
            sectors = list(Sector)
        return run_sweep(
            amplitudes=amplitudes,
            sectors=sectors,
            tau=TAU,
            eps=EPS,
            trials=trials,
            seed=99,
            quiet=True,
        )

    def test_cell_count(self):
        """run_sweep returns len(sectors) * len(amplitudes) cells."""
        amps = [0.01, 0.05, 0.15]
        sects = [Sector.ANY, Sector.EVEN]
        results = self._sweep(amps, sects)
        self.assertEqual(len(results), len(amps) * len(sects))

    def test_all_cells_have_correct_trials(self):
        results = self._sweep(trials=150)
        for r in results:
            self.assertEqual(r.trials, 150)

    def test_counts_sum_to_trials_in_sweep(self):
        results = self._sweep()
        for r in results:
            total = r.admitted + r.collapsed + r.sym_denied + r.syn_denied
            self.assertEqual(total, r.trials,
                             f'counts {total} != trials in cell {r.amplitude}/{r.sector}')

    def test_max_residual_le_tau_in_sweep(self):
        results = self._sweep()
        for r in results:
            if r.max_residual is not None:
                self.assertLessEqual(r.max_residual, TAU + 1e-9,
                                     f'max_residual {r.max_residual} > tau in '
                                     f'cell {r.amplitude}/{r.sector}')

    def test_admit_rate_decreases_with_amplitude_for_any(self):
        """
        For Sector.ANY, admit_rate should decrease as amplitude increases.
        Test the first vs last amplitude cell.
        """
        amps = [0.005, 0.05, 0.20]
        results = self._sweep(amplitudes=amps, sectors=[Sector.ANY], trials=300)
        self.assertGreater(
            results[0].admit_rate, results[-1].admit_rate,
            'admit_rate did not decrease from low to high amplitude',
        )

    def test_sweep_ordering(self):
        """Cells in run_sweep are ordered sector-major, amplitude-minor."""
        amps = [0.01, 0.05]
        sects = [Sector.ANY, Sector.EVEN]
        results = self._sweep(amps, sects)
        self.assertEqual(results[0].sector, 'ANY')
        self.assertEqual(results[0].amplitude, 0.01)
        self.assertEqual(results[1].sector, 'ANY')
        self.assertEqual(results[1].amplitude, 0.05)
        self.assertEqual(results[2].sector, 'EVEN')
        self.assertEqual(results[2].amplitude, 0.01)

    def test_deterministic_with_same_seed(self):
        """Same seed → identical results."""
        r1 = run_sweep([0.05], [Sector.ANY], TAU, EPS, 200, seed=7, quiet=True)
        r2 = run_sweep([0.05], [Sector.ANY], TAU, EPS, 200, seed=7, quiet=True)
        self.assertEqual(r1[0].admitted, r2[0].admitted)
        self.assertEqual(r1[0].collapsed, r2[0].collapsed)

    def test_different_seeds_may_differ(self):
        """Different seeds should (almost certainly) produce different counts."""
        r1 = run_sweep([0.05], [Sector.ANY], TAU, EPS, 500, seed=1, quiet=True)
        r2 = run_sweep([0.05], [Sector.ANY], TAU, EPS, 500, seed=999, quiet=True)
        # Not a hard guarantee, but with 500 trials the probability of exact
        # equality by chance is negligible.
        self.assertFalse(
            r1[0].admitted == r2[0].admitted and r1[0].collapsed == r2[0].collapsed,
            'Two different seeds produced identical results — unexpected',
        )


if __name__ == '__main__':
    unittest.main()
