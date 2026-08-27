"""Tests for membrane_shield.py — OES-32 MEMBRANE SHIELD"""
import unittest

from membrane_shield import (
    MembraneShield, ShieldDenied,
    Role, Face, Sector,
    zeros, bump, mu, residual_max, deltas, symmetry_ok, WIDTH,
)


def _calibrated_shield(tau=0.1, sector=Sector.ANY, eps=1e-9):
    """Return a shield with a committed zero-reference calibration."""
    sh = MembraneShield()
    g = sh.issue(Role.GARDIEN, 'g1')
    c = sh.issue(Role.CALIBRATEUR, 'c1')
    ref = zeros()
    pid = sh.propose_calibration(g, ref, ref, tau)
    sh.countersign_calibration(c, pid)
    sh.commit_calibration(g, pid)
    sh.set_sector(g, sector, eps)
    return sh, g, c


class TestHelpers(unittest.TestCase):
    def test_mu(self):
        self.assertEqual(mu(0), 16)
        self.assertEqual(mu(16), 0)
        self.assertEqual(mu(31), 15)

    def test_zeros_width(self):
        self.assertEqual(len(zeros()), WIDTH)

    def test_bump(self):
        v = zeros()
        v2 = bump(v, 5, 3.14)
        self.assertEqual(v2[5], 3.14)
        self.assertEqual(v2[0], 0.0)

    def test_residual_max(self):
        a = zeros()
        b = bump(zeros(), 3, 0.5)
        self.assertAlmostEqual(residual_max(a, b), 0.5)

    def test_deltas(self):
        a = bump(zeros(), 0, 1.0)
        b = zeros()
        d = deltas(a, b)
        self.assertEqual(d[0], 1.0)
        self.assertEqual(d[1], 0.0)

    def test_finite_vec_bad_width(self):
        with self.assertRaises(ShieldDenied):
            residual_max([0.0] * 5, [0.0] * 5)

    def test_finite_vec_nan(self):
        v = zeros()
        v2 = list(v)
        v2[0] = float('nan')
        with self.assertRaises(ShieldDenied):
            residual_max(v2, zeros())

    def test_finite_vec_inf(self):
        v = bump(zeros(), 1, float('inf'))
        with self.assertRaises(ShieldDenied):
            residual_max(v, zeros())

    def test_symmetry_any(self):
        self.assertTrue(symmetry_ok(zeros(), zeros(), Sector.ANY, 0.0))

    def test_symmetry_even_ok(self):
        v = zeros()
        ref = zeros()
        # delta[i] == delta[mu(i)] for all i in 0..15
        self.assertTrue(symmetry_ok(v, ref, Sector.EVEN, 0.0))

    def test_symmetry_even_fail(self):
        v = bump(zeros(), 0, 1.0)  # delta[0]=1, delta[16]=0 → violation
        self.assertFalse(symmetry_ok(v, zeros(), Sector.EVEN, 1e-9))

    def test_symmetry_odd_ok(self):
        v = zeros()
        # All deltas zero → trivially ok for odd too (0 == -0)
        self.assertTrue(symmetry_ok(v, zeros(), Sector.ODD, 0.0))

    def test_symmetry_odd_fail(self):
        # delta[i] must equal -delta[mu(i)]; bump i=0 by 1 while mu(0)=16 stays 0 → fail
        v = bump(zeros(), 0, 1.0)
        self.assertFalse(symmetry_ok(v, zeros(), Sector.ODD, 1e-9))

    def test_symmetry_fold8_ok(self):
        self.assertTrue(symmetry_ok(zeros(), zeros(), Sector.FOLD8, 0.0))

    def test_symmetry_eps_negative(self):
        with self.assertRaises(ShieldDenied):
            symmetry_ok(zeros(), zeros(), Sector.EVEN, -1.0)


class TestIssueRevoke(unittest.TestCase):
    def setUp(self):
        self.sh = MembraneShield()

    def test_issue_roles(self):
        for role in Role:
            cap = self.sh.issue(role, f'agent_{role.value}')
            self.assertEqual(cap.role, role)

    def test_invalid_agent_id_empty(self):
        with self.assertRaises(ShieldDenied):
            self.sh.issue(Role.OBSERVATEUR, '')

    def test_invalid_agent_id_too_long(self):
        with self.assertRaises(ShieldDenied):
            self.sh.issue(Role.OBSERVATEUR, 'x' * 65)

    def test_revoke_requires_gardien(self):
        g = self.sh.issue(Role.GARDIEN, 'grd')
        obs = self.sh.issue(Role.OBSERVATEUR, 'obs')
        with self.assertRaises(ShieldDenied):
            self.sh.revoke(obs, 'grd')

    def test_revoke_works(self):
        g = self.sh.issue(Role.GARDIEN, 'grd')
        obs = self.sh.issue(Role.OBSERVATEUR, 'obs')
        self.sh.revoke(g, 'obs')
        # obs cap is now revoked
        with self.assertRaises(ShieldDenied):
            self.sh.observe(obs)

    def test_forged_cap_rejected(self):
        import dataclasses
        g = self.sh.issue(Role.GARDIEN, 'grd')
        forged = dataclasses.replace(g, secret=b'\x00' * 32)
        with self.assertRaises(ShieldDenied):
            self.sh.latch(forged)


class TestObserve(unittest.TestCase):
    def setUp(self):
        self.sh = MembraneShield()

    def test_observateur_boundary_ok(self):
        obs = self.sh.issue(Role.OBSERVATEUR, 'obs')
        data = self.sh.observe(obs, Face.BOUNDARY)
        self.assertEqual(len(data), WIDTH)

    def test_observateur_bulk_denied(self):
        obs = self.sh.issue(Role.OBSERVATEUR, 'obs')
        with self.assertRaises(ShieldDenied):
            self.sh.observe(obs, Face.BULK)

    def test_gardien_bulk_ok(self):
        g = self.sh.issue(Role.GARDIEN, 'grd')
        data = self.sh.observe(g, Face.BULK)
        self.assertEqual(len(data), WIDTH)


class TestCalibration(unittest.TestCase):
    def _make_shield(self):
        sh = MembraneShield()
        g = sh.issue(Role.GARDIEN, 'g1')
        c = sh.issue(Role.CALIBRATEUR, 'c1')
        return sh, g, c

    def test_full_calibration_flow(self):
        sh, g, c = self._make_shield()
        ref = zeros()
        pid = sh.propose_calibration(g, ref, ref, 0.1)
        sh.countersign_calibration(c, pid)
        sh.commit_calibration(g, pid)
        self.assertFalse(sh.state.locked)
        self.assertAlmostEqual(sh.state.tau, 0.1)

    def test_commit_without_seal_fails(self):
        sh, g, c = self._make_shield()
        ref = zeros()
        pid = sh.propose_calibration(g, ref, ref, 0.1)
        with self.assertRaises(ShieldDenied):
            sh.commit_calibration(g, pid)

    def test_same_agent_countersign_non_gardien(self):
        sh = MembraneShield()
        g = sh.issue(Role.GARDIEN, 'g1')
        c = sh.issue(Role.CALIBRATEUR, 'c1')
        ref = zeros()
        pid = sh.propose_calibration(c, ref, ref, 0.1)
        with self.assertRaises(ShieldDenied):
            sh.countersign_calibration(c, pid)  # same non-gardien agent

    def test_gardien_self_countersign_ok(self):
        sh, g, c = self._make_shield()
        ref = zeros()
        pid = sh.propose_calibration(g, ref, ref, 0.1)
        sh.countersign_calibration(g, pid)  # gardien may countersign own proposal
        sh.commit_calibration(g, pid)
        self.assertFalse(sh.state.locked)

    def test_wrong_proposal_id(self):
        sh, g, c = self._make_shield()
        ref = zeros()
        sh.propose_calibration(g, ref, ref, 0.1)
        with self.assertRaises(ShieldDenied):
            sh.countersign_calibration(c, 'deadbeef')

    def test_tau_nan_rejected(self):
        sh, g, _ = self._make_shield()
        with self.assertRaises(ShieldDenied):
            sh.propose_calibration(g, zeros(), zeros(), float('nan'))

    def test_tau_negative_rejected(self):
        sh, g, _ = self._make_shield()
        with self.assertRaises(ShieldDenied):
            sh.propose_calibration(g, zeros(), zeros(), -0.01)

    def test_observateur_cannot_propose(self):
        sh, g, _ = self._make_shield()
        obs = sh.issue(Role.OBSERVATEUR, 'obs')
        with self.assertRaises(ShieldDenied):
            sh.propose_calibration(obs, zeros(), zeros(), 0.1)


class TestFlip(unittest.TestCase):
    def _ready(self, tau=0.1):
        return _calibrated_shield(tau=tau)

    def test_flip_ok(self):
        sh, g, c = self._ready()
        dec = sh.issue(Role.DECODEUR, 'dec')
        new_b = bump(zeros(), 0, 0.05)
        frame = sh.request_flip(dec, new_b, syndrome_ok=True)
        self.assertEqual(frame.boundary[0], 0.05)

    def test_flip_locked(self):
        sh = MembraneShield()
        g = sh.issue(Role.GARDIEN, 'grd')
        dec = sh.issue(Role.DECODEUR, 'dec')
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, zeros(), syndrome_ok=True)

    def test_flip_syndrome_rejected(self):
        sh, g, c = self._ready()
        dec = sh.issue(Role.DECODEUR, 'dec')
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, zeros(), syndrome_ok=False)

    def test_flip_logical_rejected(self):
        sh, g, c = self._ready()
        dec = sh.issue(Role.DECODEUR, 'dec')
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, zeros(), syndrome_ok=True, logical_ok=False)

    def test_flip_residual_breach(self):
        sh, g, c = self._ready(tau=0.01)
        dec = sh.issue(Role.DECODEUR, 'dec')
        big = bump(zeros(), 0, 0.5)  # residual 0.5 >> tau 0.01
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, big, syndrome_ok=True)
        self.assertTrue(sh.state.collapse)

    def test_flip_after_collapse_denied(self):
        sh, g, c = self._ready(tau=0.01)
        dec = sh.issue(Role.DECODEUR, 'dec')
        big = bump(zeros(), 0, 0.5)
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, big, syndrome_ok=True)
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, zeros(), syndrome_ok=True)

    def test_observateur_cannot_flip(self):
        sh, g, c = self._ready()
        obs = sh.issue(Role.OBSERVATEUR, 'obs')
        with self.assertRaises(ShieldDenied):
            sh.request_flip(obs, zeros(), syndrome_ok=True)

    def test_flip_symmetry_even_fail(self):
        sh, g, c = _calibrated_shield(tau=1.0, sector=Sector.EVEN, eps=1e-9)
        dec = sh.issue(Role.DECODEUR, 'dec')
        # delta[0]=0.1 but delta[mu(0)=16]=0 → even symmetry fails
        asym = bump(zeros(), 0, 0.05)
        with self.assertRaises(ShieldDenied):
            sh.request_flip(dec, asym, syndrome_ok=True)

    def test_flip_symmetry_even_ok(self):
        sh, g, c = _calibrated_shield(tau=1.0, sector=Sector.EVEN, eps=1e-9)
        dec = sh.issue(Role.DECODEUR, 'dec')
        # Make delta[i] == delta[mu(i)] for all pairs
        sym = list(zeros())
        for i in range(WIDTH // 2):
            sym[i] = 0.05
            sym[mu(i)] = 0.05
        frame = sh.request_flip(dec, sym, syndrome_ok=True)
        self.assertIsNotNone(frame)

    def test_flip_symmetry_odd_ok(self):
        sh, g, c = _calibrated_shield(tau=1.0, sector=Sector.ODD, eps=1e-9)
        dec = sh.issue(Role.DECODEUR, 'dec')
        # delta[i] == -delta[mu(i)]
        sym = list(zeros())
        for i in range(WIDTH // 2):
            sym[i] = 0.05
            sym[mu(i)] = -0.05
        frame = sh.request_flip(dec, sym, syndrome_ok=True)
        self.assertIsNotNone(frame)

    def test_flip_symmetry_fold8_ok(self):
        sh, g, c = _calibrated_shield(tau=1.0, sector=Sector.FOLD8, eps=1e-9)
        dec = sh.issue(Role.DECODEUR, 'dec')
        # All zeros is trivially fold8 symmetric
        frame = sh.request_flip(dec, zeros(), syndrome_ok=True)
        self.assertIsNotNone(frame)


class TestLatchReset(unittest.TestCase):
    def test_manual_latch(self):
        sh, g, _ = _calibrated_shield()
        sh.latch(g, 'test')
        self.assertTrue(sh.state.collapse)
        self.assertTrue(sh.state.locked)

    def test_reset_after_latch(self):
        sh, g, _ = _calibrated_shield()
        sh.latch(g)
        sh.reset_after_latch(g)
        self.assertFalse(sh.state.collapse)
        self.assertFalse(sh.state.locked)

    def test_observateur_cannot_latch(self):
        sh, g, _ = _calibrated_shield()
        obs = sh.issue(Role.OBSERVATEUR, 'obs')
        with self.assertRaises(ShieldDenied):
            sh.latch(obs)


class TestAudit(unittest.TestCase):
    def test_audit_populated(self):
        sh, g, _ = _calibrated_shield()
        self.assertGreater(len(sh.state.audit), 0)

    def test_audit_admitted_flip(self):
        sh, g, _ = _calibrated_shield()
        dec = sh.issue(Role.DECODEUR, 'dec')
        sh.request_flip(dec, zeros(), syndrome_ok=True)
        flip_events = [e for e in sh.state.audit if e.action == 'flip' and e.admitted]
        self.assertEqual(len(flip_events), 1)

    def test_audit_denied_flip(self):
        sh, g, _ = _calibrated_shield()
        dec = sh.issue(Role.DECODEUR, 'dec')
        try:
            sh.request_flip(dec, zeros(), syndrome_ok=False)
        except ShieldDenied:
            pass
        denied = [e for e in sh.state.audit if e.action == 'flip' and not e.admitted]
        self.assertEqual(len(denied), 1)


class TestSetSector(unittest.TestCase):
    def test_set_sector(self):
        sh, g, _ = _calibrated_shield()
        sh.set_sector(g, Sector.EVEN, 1e-6)
        self.assertEqual(sh.state.sector, Sector.EVEN)
        self.assertAlmostEqual(sh.state.symmetry_eps, 1e-6)

    def test_set_sector_bad_eps(self):
        sh, g, _ = _calibrated_shield()
        with self.assertRaises(ShieldDenied):
            sh.set_sector(g, Sector.EVEN, -1.0)

    def test_non_gardien_cannot_set_sector(self):
        sh, g, _ = _calibrated_shield()
        dec = sh.issue(Role.DECODEUR, 'dec')
        with self.assertRaises(ShieldDenied):
            sh.set_sector(dec, Sector.EVEN)


if __name__ == '__main__':
    unittest.main()
