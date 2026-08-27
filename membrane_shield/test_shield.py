import unittest

from membrane_shield.membrane_shield import MembraneShield, PolicyError


class MembraneShieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shield = MembraneShield()
        self.c = [1] * 32
        self.H_identity = [[1 if i == j else 0 for j in range(32)] for i in range(32)]

    def test_width32_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.shield.observateur_copy_B([1] * 31)

    def test_finite_floats_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.shield.request_flip(self.H_identity, self.c, self.c, float("nan"), 0.1)

    def test_observateur_rejects_u_or_f_access(self) -> None:
        with self.assertRaises(PolicyError):
            self.shield.observateur_copy_B([0] * 32, U=[1] * 32)

    def test_calibrateur_is_quarantine_only(self) -> None:
        with self.assertRaises(PolicyError):
            self.shield.calibrateur_action("calibrateur", "commit")

    def test_calibrateur_requires_distinct_countersigner(self) -> None:
        with self.assertRaises(PolicyError):
            self.shield.require_distinct_countersign("calibrateur", "calibrateur")

    def test_only_gardien_can_commit(self) -> None:
        with self.assertRaises(PolicyError):
            self.shield.guard_commit("calibrateur")

    def test_request_flip_requires_computed_parity_match(self) -> None:
        bad_s = [0] * 32
        with self.assertRaises(PolicyError):
            self.shield.request_flip(self.H_identity, self.c, bad_s, residual=0.01, tau=0.1)

    def test_residual_breach_latches_collapse(self) -> None:
        with self.assertRaises(PolicyError):
            self.shield.request_flip(self.H_identity, self.c, self.c, residual=0.2, tau=0.1)
        self.assertTrue(self.shield.collapsed)
        with self.assertRaises(PolicyError):
            self.shield.request_flip(self.H_identity, self.c, self.c, residual=0.01, tau=0.1)

    def test_only_gardien_resets_to_last_sealed_reference(self) -> None:
        self.shield.seal_reference("gardien", [0] * 32)
        with self.assertRaises(PolicyError):
            self.shield.request_flip(self.H_identity, self.c, self.c, residual=0.2, tau=0.1)
        restored = self.shield.reset_to_last_sealed_reference("gardien")
        self.assertEqual(restored, [0] * 32)
        self.assertFalse(self.shield.collapsed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
