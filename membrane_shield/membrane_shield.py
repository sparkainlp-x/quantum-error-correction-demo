"""Membrane shield policy checks for guarded decoder operations."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, List, Sequence


class PolicyError(PermissionError):
    """Raised when a membrane policy rule is violated."""


@dataclass
class MembraneShield:
    """Policy boundary that enforces privilege and safety constraints."""

    collapsed: bool = False
    sealed_reference: Sequence[int] | None = None

    def _deny(self, message: str) -> None:
        raise PolicyError(message)

    @staticmethod
    def _validate_width32(vec: Sequence[int], label: str) -> None:
        if len(vec) != 32:
            raise ValueError(f"{label} must have width 32")
        if any(bit not in (0, 1, False, True) for bit in vec):
            raise ValueError(f"{label} must be binary")

    @staticmethod
    def _validate_finite(values: Iterable[float], label: str) -> None:
        for v in values:
            if not isfinite(float(v)):
                raise ValueError(f"{label} contains non-finite value")

    @staticmethod
    def _mat_vec_mod2(H: Sequence[Sequence[int]], c: Sequence[int]) -> List[int]:
        out: List[int] = []
        for row in H:
            if len(row) != len(c):
                raise ValueError("H and c dimensions are incompatible")
            parity = sum((int(a) & 1) * (int(b) & 1) for a, b in zip(row, c)) % 2
            out.append(parity)
        return out

    def observateur_copy_B(
        self,
        B: Sequence[int],
        *,
        U: Sequence[int] | None = None,
        F: Sequence[int] | None = None,
    ) -> List[int]:
        """Return a copy of B and reject access to U/F."""
        self._validate_width32(B, "B")
        if U is not None or F is not None:
            self._deny("observateur may access a copy of B only")
        return [int(x) & 1 for x in B]

    def calibrateur_action(self, actor: str, action: str) -> str:
        """Allow calibrateur quarantine action only."""
        if actor != "calibrateur":
            self._deny("only calibrateur may invoke calibrateur action")
        if action != "quarantine":
            self._deny("calibrateur is restricted to quarantine only")
        return "quarantine-approved"

    def require_distinct_countersign(self, actor: str, countersigner: str) -> bool:
        """Require a different countersigner for calibrateur actions."""
        if actor != "calibrateur":
            self._deny("countersign check applies to calibrateur actions")
        if not countersigner or countersigner == actor:
            self._deny("countersigner must be different from calibrateur")
        return True

    def guard_commit(self, actor: str) -> bool:
        """Allow commit-level authority to gardien only."""
        if actor != "gardien":
            self._deny("only gardien may commit")
        return True

    def request_flip(
        self,
        H: Sequence[Sequence[int]],
        c: Sequence[int],
        s: Sequence[int],
        residual: float,
        tau: float,
    ) -> bool:
        """Allow decoder flip request only when parity and residual checks pass."""
        if self.collapsed:
            self._deny("collapse latch is active")

        self._validate_width32(c, "c")
        self._validate_finite((residual, tau), "residual/tau")

        expected = self._mat_vec_mod2(H, c)
        syndrome = [int(x) & 1 for x in s]
        if expected != syndrome:
            self._deny("request_flip denied: H*c != s")

        if residual > tau:
            self.collapsed = True
            self._deny("residual breach latched collapse")

        return True

    def seal_reference(self, actor: str, reference: Sequence[int]) -> bool:
        """Store a sealed reference using gardien authority."""
        self.guard_commit(actor)
        self._validate_width32(reference, "reference")
        self.sealed_reference = [int(x) & 1 for x in reference]
        return True

    def reset_to_last_sealed_reference(self, actor: str) -> Sequence[int]:
        """Reset collapse latch using gardien authority and sealed reference."""
        self.guard_commit(actor)
        if self.sealed_reference is None:
            self._deny("no sealed reference available")
        self.collapsed = False
        return list(self.sealed_reference)
