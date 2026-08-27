#!/usr/bin/env python3
"""Contract tests for the membrane shield."""

from __future__ import annotations

import unittest

from membrane_shield import WIDTH, Face, MembraneShield, Role, ShieldDenied


def zero_vec():
    return [0.0] * WIDTH


def bump(vec, i, value):
    out = list(vec)
    out[i] = value
    return out


def h_identity():
    return [[1 if i == j else 0 for j in range(WIDTH)] for i in range(WIDTH)]


def bits_from_boundary(vec):
    return [1 if x >= 0.5 else 0 for x in vec]


def compute_syndrome_ok(H, correction, syndrome):
    computed = []
    for i in range(WIDTH):
        computed.append(sum(H[i][j] * correction[j] for j in range(WIDTH)) % 2)
    return computed == list(syndrome)


class ShieldTests(unittest.TestCase):
    def setUp(self):
        self.s = MembraneShield(token_ttl_s=3600)
        self.H = h_identity()
        self.zero_bits = [0] * WIDTH
        self.g = self.s.issue(Role.GARDIEN, "gardien-0")
        self.o = self.s.issue(Role.OBSERVATEUR, "oeil-1")
        self.c1 = self.s.issue(Role.CALIBRATEUR, "cal-a")
        self.c2 = self.s.issue(Role.CALIBRATEUR, "cal-b")
        self.d = self.s.issue(Role.DECODEUR, "dec-0")

    def _arm(self, tau=0.2):
        pid = self.s.propose_calibration(self.c1, zero_vec(), zero_vec(), tau)
        self.s.countersign_calibration(self.c2, pid)
        self.s.commit_calibration(self.g, pid)

    def test_observateur_reads_boundary_copy_only(self):
        self._arm()
        b = self.s.observe(self.o, Face.BOUNDARY)
        self.assertEqual(len(b), WIDTH)
        with self.assertRaises(ShieldDenied):
            self.s.observe(self.o, Face.BULK)

    def test_observateur_cannot_flip(self):
        self._arm()
        syndrome_ok = compute_syndrome_ok(self.H, self.zero_bits, self.zero_bits)
        with self.assertRaises(ShieldDenied):
            self.s.request_flip(self.o, zero_vec(), syndrome_ok=syndrome_ok, H=self.H, correction=self.zero_bits, syndrome=self.zero_bits)

    def test_calibrator_cannot_commit_alone(self):
        pid = self.s.propose_calibration(self.c1, zero_vec(), zero_vec(), 0.1)
        with self.assertRaises(ShieldDenied):
            self.s.countersign_calibration(self.c1, pid)
        with self.assertRaises(ShieldDenied):
            self.s.commit_calibration(self.c1, pid)

    def test_dual_control_then_flip_admitted(self):
        self._arm(tau=0.5)
        new_b = bump(zero_vec(), 0, 0.1)
        corr = bits_from_boundary(new_b)
        syndrome_ok = compute_syndrome_ok(self.H, corr, corr)
        live = self.s.request_flip(self.d, new_b, syndrome_ok=syndrome_ok, H=self.H, correction=corr, syndrome=corr)
        self.assertEqual(live.boundary[0], 0.1)
        self.assertEqual(live.bulk[0], 0.1)

    def test_syndrome_reject(self):
        self._arm()
        bad_s = [1] * WIDTH
        syndrome_ok = compute_syndrome_ok(self.H, self.zero_bits, bad_s)
        with self.assertRaises(ShieldDenied):
            self.s.request_flip(self.d, zero_vec(), syndrome_ok=syndrome_ok, H=self.H, correction=self.zero_bits, syndrome=bad_s)

    def test_residual_latch(self):
        self._arm(tau=0.05)
        new_b = bump(zero_vec(), 3, 1.0)
        corr = bits_from_boundary(new_b)
        syndrome_ok = compute_syndrome_ok(self.H, corr, corr)
        with self.assertRaises(ShieldDenied):
            self.s.request_flip(self.d, new_b, syndrome_ok=syndrome_ok, H=self.H, correction=corr, syndrome=corr)
        self.assertTrue(self.s.state.collapse)
        syndrome_ok2 = compute_syndrome_ok(self.H, self.zero_bits, self.zero_bits)
        with self.assertRaises(ShieldDenied):
            self.s.request_flip(self.d, zero_vec(), syndrome_ok=syndrome_ok2, H=self.H, correction=self.zero_bits, syndrome=self.zero_bits)

    def test_reset_requires_gardien(self):
        self._arm(tau=0.05)
        try:
            new_b = bump(zero_vec(), 3, 1.0)
            corr = bits_from_boundary(new_b)
            syndrome_ok = compute_syndrome_ok(self.H, corr, corr)
            self.s.request_flip(self.d, new_b, syndrome_ok=syndrome_ok, H=self.H, correction=corr, syndrome=corr)
        except ShieldDenied:
            pass
        with self.assertRaises(ShieldDenied):
            self.s.reset_after_latch(self.d)
        self.s.reset_after_latch(self.g)
        self.assertFalse(self.s.state.collapse)
        self.assertEqual(self.s.observe(self.o, Face.BOUNDARY), tuple(zero_vec()))

    def test_forged_or_expired_denied(self):
        self._arm()
        self.s.revoke(self.g, "dec-0")
        syndrome_ok = compute_syndrome_ok(self.H, self.zero_bits, self.zero_bits)
        with self.assertRaises(ShieldDenied):
            self.s.request_flip(self.d, zero_vec(), syndrome_ok=syndrome_ok, H=self.H, correction=self.zero_bits, syndrome=self.zero_bits)

    def test_reject_nonfinite(self):
        with self.assertRaises(ShieldDenied):
            self.s.propose_calibration(self.c1, zero_vec(), [float("nan")] * WIDTH, 0.1)


if __name__ == "__main__":
    unittest.main()
