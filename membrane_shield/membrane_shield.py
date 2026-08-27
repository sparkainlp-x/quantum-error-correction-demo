#!/usr/bin/env python3
"""
Membrane Shield — fail-closed protection around the holographic membrane,
the observateur, and calibration agents.

Scope: software isolation and admission control for the 32-slot two-faced
register. Not a physical weapon, not a medical device, not a physics claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from time import perf_counter_ns, time_ns
from typing import FrozenSet, Optional
import hmac
import secrets

WIDTH = 32


class Role(str, Enum):
    OBSERVATEUR = "observateur"
    CALIBRATEUR = "calibrateur"
    DECODEUR = "decodeur"
    GARDIEN = "gardien"


class Face(str, Enum):
    BULK = "U"
    BOUNDARY = "B"


class Sector(str, Enum):
    ANY = "ANY"
    EVEN = "EVEN"
    ODD = "ODD"
    FOLD8 = "FOLD8"


class ShieldDenied(Exception):
    """Fail-closed: every unauthorized or malformed act raises this."""


def mu(i: int) -> int:
    """Möbius index map: mu(i) = (i + 16) mod 32."""
    return (int(i) + 16) % WIDTH


def sigma(i: int) -> int:
    """Fold index map: sigma(i) = (i + 4) mod 32."""
    return (int(i) + 4) % WIDTH


def _finite_vec(name: str, vec) -> tuple[float, ...]:
    if vec is None:
        raise ShieldDenied(f"{name}: missing")
    try:
        out = tuple(float(x) for x in vec)
    except (TypeError, ValueError) as exc:
        raise ShieldDenied(f"{name}: not real-valued") from exc
    if len(out) != WIDTH:
        raise ShieldDenied(f"{name}: width {len(out)} != {WIDTH}")
    if any(x != x or x in (float("inf"), float("-inf")) for x in out):
        raise ShieldDenied(f"{name}: non-finite component")
    return out


def residual_max(observed, reference) -> float:
    obs = _finite_vec("observed", observed)
    ref = _finite_vec("reference", reference)
    return max(abs(o - r) for o, r in zip(obs, ref))


def symmetry_sector(observed_boundary, reference_boundary) -> tuple[int, ...]:
    obs = _finite_vec("observed_boundary", observed_boundary)
    ref = _finite_vec("reference_boundary", reference_boundary)
    out: list[int] = []
    for o, r in zip(obs, ref):
        if o > r:
            out.append(1)
        elif o < r:
            out.append(-1)
        else:
            out.append(0)
    return tuple(out)


def symmetry_ok(
    observed_boundary,
    reference_boundary,
    *,
    declared_pattern=None,
    declared_sector: Sector | str = Sector.ANY,
) -> bool:
    pattern = symmetry_sector(observed_boundary, reference_boundary)
    if declared_pattern is not None:
        try:
            declared = tuple(int(x) for x in declared_pattern)
        except (TypeError, ValueError):
            return False
        if len(declared) != WIDTH or any(x not in (-1, 0, 1) for x in declared):
            return False
        if pattern != declared:
            return False

    sector = declared_sector if isinstance(declared_sector, Sector) else Sector(str(declared_sector))
    if sector is Sector.ANY:
        return True
    if sector is Sector.EVEN:
        return all(v == 0 or (i % 2 == 0) for i, v in enumerate(pattern))
    if sector is Sector.ODD:
        return all(v == 0 or (i % 2 == 1) for i, v in enumerate(pattern))
    # FOLD8: invariance under sigma (period-4 class consistency)
    return all(pattern[i] == pattern[sigma(i)] for i in range(WIDTH))


def _finite_binary32(name: str, vec) -> tuple[int, ...]:
    bits = _finite_vec(name, vec)
    if any(x not in (0.0, 1.0) for x in bits):
        raise ShieldDenied(f"{name}: non-binary component")
    return tuple(int(x) for x in bits)


@dataclass(frozen=True)
class Capability:
    role: Role
    agent_id: str
    allowed_faces: FrozenSet[Face]
    can_read: bool
    can_propose_calibration: bool
    can_request_flip: bool
    can_commit: bool
    _secret: bytes = field(repr=False)
    issued_ns: int
    expires_ns: int

    def expired(self, now_ns: Optional[int] = None) -> bool:
        return (time_ns() if now_ns is None else now_ns) >= self.expires_ns

@dataclass(frozen=True)
class MembraneFrame:
    bulk: tuple[float, ...]
    boundary: tuple[float, ...]

    @classmethod
    def zeros(cls) -> "MembraneFrame":
        z = tuple(0.0 for _ in range(WIDTH))
        return cls(bulk=z, boundary=z)

    def snapshot(self) -> "MembraneFrame":
        return MembraneFrame(bulk=self.bulk, boundary=self.boundary)


@dataclass(frozen=True)
class DecodeReport:
    syndrome_ok: bool
    logical_ok: bool
    iterations: int
    latency_ns: int
    residual: float


@dataclass
class CalibrationProposal:
    proposal_id: str
    agent_id: str
    reference: MembraneFrame
    tau: float
    sealed: bool = False
    countersign_agent: Optional[str] = None


@dataclass
class AuditEvent:
    ns: int
    agent_id: str
    role: str
    action: str
    admitted: bool
    detail: str


@dataclass
class ShieldState:
    live: MembraneFrame = field(default_factory=MembraneFrame.zeros)
    reference: MembraneFrame = field(default_factory=MembraneFrame.zeros)
    tau: float = 0.05
    locked: bool = True
    collapse: bool = False
    pending: Optional[CalibrationProposal] = None
    audit: list[AuditEvent] = field(default_factory=list)


class MembraneShield:
    def __init__(self, master: Optional[bytes] = None, token_ttl_s: int = 3600):
        self._master = master or secrets.token_bytes(32)
        self._token_ttl_ns = int(token_ttl_s * 1e9)
        self._caps: dict[str, Capability] = {}
        self.state = ShieldState()

    def _audit(self, cap: Optional[Capability], action: str, admitted: bool, detail: str) -> None:
        self.state.audit.append(
            AuditEvent(
                ns=time_ns(),
                agent_id=cap.agent_id if cap else "-",
                role=cap.role.value if cap else "-",
                action=action,
                admitted=admitted,
                detail=detail[:240],
            )
        )

    def _need(self, cap: Capability, *, write=False, flip=False, calib=False, commit=False) -> None:
        if cap.expired():
            raise ShieldDenied("capability expired")
        stored = self._caps.get(cap.agent_id)
        if stored is None or stored._secret != cap._secret or stored.role != cap.role:
            raise ShieldDenied("capability revoked or forged")
        if self.state.collapse and flip:
            raise ShieldDenied("membrane collapsed — shield latched")
        if write and not cap.can_commit and not cap.can_request_flip:
            raise ShieldDenied("no write privilege")
        if flip and not cap.can_request_flip:
            raise ShieldDenied("no flip privilege")
        if calib and not cap.can_propose_calibration:
            raise ShieldDenied("no calibration privilege")
        if commit and not cap.can_commit:
            raise ShieldDenied("no commit privilege")

    def issue(self, role: Role, agent_id: str) -> Capability:
        if not agent_id or not agent_id.isprintable() or len(agent_id) > 64:
            raise ShieldDenied("invalid agent_id")
        now = time_ns()
        if role is Role.OBSERVATEUR:
            cap = Capability(
                role=role, agent_id=agent_id,
                allowed_faces=frozenset({Face.BOUNDARY}),
                can_read=True, can_propose_calibration=False,
                can_request_flip=False, can_commit=False,
                _secret=hmac.new(self._master, f"obs|{agent_id}|{now}".encode(), sha256).digest(),
                issued_ns=now, expires_ns=now + self._token_ttl_ns,
            )
        elif role is Role.CALIBRATEUR:
            cap = Capability(
                role=role, agent_id=agent_id,
                allowed_faces=frozenset({Face.BOUNDARY, Face.BULK}),
                can_read=True, can_propose_calibration=True,
                can_request_flip=False, can_commit=False,
                _secret=hmac.new(self._master, f"cal|{agent_id}|{now}".encode(), sha256).digest(),
                issued_ns=now, expires_ns=now + self._token_ttl_ns,
            )
        elif role is Role.DECODEUR:
            cap = Capability(
                role=role, agent_id=agent_id,
                allowed_faces=frozenset({Face.BOUNDARY}),
                can_read=True, can_propose_calibration=False,
                can_request_flip=True, can_commit=False,
                _secret=hmac.new(self._master, f"dec|{agent_id}|{now}".encode(), sha256).digest(),
                issued_ns=now, expires_ns=now + self._token_ttl_ns,
            )
        elif role is Role.GARDIEN:
            cap = Capability(
                role=role, agent_id=agent_id,
                allowed_faces=frozenset({Face.BOUNDARY, Face.BULK}),
                can_read=True, can_propose_calibration=True,
                can_request_flip=True, can_commit=True,
                _secret=hmac.new(self._master, f"grd|{agent_id}|{now}".encode(), sha256).digest(),
                issued_ns=now, expires_ns=now + self._token_ttl_ns,
            )
        else:
            raise ShieldDenied("unknown role")
        self._caps[agent_id] = cap
        self._audit(cap, "issue", True, role.value)
        return cap

    def revoke(self, gardien: Capability, agent_id: str) -> None:
        self._need(gardien, commit=True)
        self._caps.pop(agent_id, None)
        self._audit(gardien, "revoke", True, agent_id)

    def observe(self, cap: Capability, face: Face = Face.BOUNDARY) -> tuple[float, ...]:
        self._need(cap)
        if not cap.can_read:
            self._audit(cap, "observe", False, "no read")
            raise ShieldDenied("no read privilege")
        if face not in cap.allowed_faces:
            self._audit(cap, "observe", False, f"face {face.value} forbidden")
            raise ShieldDenied(f"observateur cannot read face {face.value}")
        src = self.state.live.bulk if face is Face.BULK else self.state.live.boundary
        copy = tuple(src)
        self._audit(cap, "observe", True, face.value)
        return copy

    def propose_calibration(self, cap, reference_bulk, reference_boundary, tau: float) -> str:
        self._need(cap, calib=True)
        if tau != tau or tau < 0 or tau in (float("inf"), float("-inf")):
            raise ShieldDenied("tau must be finite and >= 0")
        ref = MembraneFrame(
            bulk=_finite_vec("U*", reference_bulk),
            boundary=_finite_vec("B*", reference_boundary),
        )
        pid = secrets.token_hex(8)
        self.state.pending = CalibrationProposal(
            proposal_id=pid, agent_id=cap.agent_id, reference=ref, tau=float(tau), sealed=False
        )
        self._audit(cap, "propose_calibration", True, f"{pid} tau={tau}")
        return pid

    def countersign_calibration(self, cap, proposal_id: str) -> None:
        self._need(cap, calib=True)
        p = self.state.pending
        if p is None or p.proposal_id != proposal_id:
            raise ShieldDenied("no such calibration proposal")
        if p.agent_id == cap.agent_id and cap.role is not Role.GARDIEN:
            raise ShieldDenied("dual-control: same agent cannot countersign")
        p.sealed = True
        p.countersign_agent = cap.agent_id
        self._audit(cap, "countersign", True, proposal_id)

    def commit_calibration(self, gardien, proposal_id: str) -> None:
        self._need(gardien, commit=True)
        p = self.state.pending
        if p is None or p.proposal_id != proposal_id:
            raise ShieldDenied("no such calibration proposal")
        if not p.sealed:
            raise ShieldDenied("calibration not sealed — dual-control required")
        self.state.reference = p.reference
        self.state.tau = p.tau
        self.state.pending = None
        self.state.locked = False
        self._audit(gardien, "commit_calibration", True, proposal_id)

    def request_flip(
        self,
        cap,
        new_boundary,
        *,
        H=None,
        correction=None,
        syndrome=None,
        declared_pattern=None,
        declared_sector: Sector | str = Sector.ANY,
        logical_ok: bool,
    ) -> MembraneFrame:
        """Request paired membrane flip; admission uses computed Hc==s, residual<=tau, and symmetry-pattern match."""
        self._need(cap, flip=True)
        if self.state.locked:
            self._audit(cap, "flip", False, "shield locked — no live calibration")
            raise ShieldDenied("shield locked until calibration is committed")
        if H is None or correction is None or syndrome is None:
            self._audit(cap, "flip", False, "missing syndrome proof")
            raise ShieldDenied("syndrome proof required (computed Hc == s)")
        syndrome_ok = _h_mul_mod2(H, correction) == _finite_binary32("syndrome", syndrome)
        proposed_b = _finite_vec("B'", new_boundary)
        symmetry_ok_flag = symmetry_ok(
            proposed_b,
            self.state.reference.boundary,
            declared_pattern=declared_pattern,
            declared_sector=declared_sector,
        )

        delta = tuple(pb - ob for pb, ob in zip(proposed_b, self.state.live.boundary))
        proposed_u = _finite_vec("U'", tuple(u + d for u, d in zip(self.state.live.bulk, delta)))

        r_b = residual_max(proposed_b, self.state.reference.boundary)
        r_u = residual_max(proposed_u, self.state.reference.bulk)
        agg = max(r_b, r_u)
        residual_ok = agg <= self.state.tau
        admitted = syndrome_ok and residual_ok and symmetry_ok_flag
        if not admitted:
            if not residual_ok:
                self.state.collapse = True
                self._audit(cap, "flip", False, f"residual {agg} > tau {self.state.tau}; latched")
                raise ShieldDenied("residual breach — shield latched (collapse)")
            if not syndrome_ok:
                self._audit(cap, "flip", False, "syndrome rejected")
                raise ShieldDenied("syndrome not admitted (Hc != s)")
            if not symmetry_ok_flag:
                self._audit(cap, "flip", False, "symmetry sector mismatch")
                raise ShieldDenied("symmetry sector mismatch")
        if not logical_ok:
            self._audit(cap, "flip", False, "logical check failed")
            raise ShieldDenied("logical operator would be flipped")

        self.state.live = MembraneFrame(bulk=proposed_u, boundary=proposed_b)
        self._audit(cap, "flip", True, f"residual={agg:.6g}")
        return self.state.live.snapshot()

    def latch(self, gardien, reason: str = "manual") -> None:
        self._need(gardien, commit=True)
        self.state.collapse = True
        self.state.locked = True
        self._audit(gardien, "latch", True, reason)

    def reset_after_latch(self, gardien) -> None:
        self._need(gardien, commit=True)
        self.state.live = self.state.reference.snapshot()
        self.state.collapse = False
        self.state.locked = False
        self.state.pending = None
        self._audit(gardien, "reset", True, "restored to reference")


def _h_mul_mod2(H, correction) -> tuple[int, ...]:
    c = _finite_binary32("correction", correction)
    rows = tuple(tuple(int(x) for x in row) for row in H)
    if len(rows) != WIDTH or any(len(row) != WIDTH for row in rows):
        raise ShieldDenied("H must be 32x32")
    if any(x not in (0, 1) for row in rows for x in row):
        raise ShieldDenied("H must be binary")
    return tuple(sum((rows[i][j] & 1) * (c[j] & 1) for j in range(WIDTH)) % 2 for i in range(WIDTH))


def membrane_decode(
    observed: MembraneFrame,
    reference: MembraneFrame,
    tau: float,
) -> DecodeReport:
    """Decoder ABI-compatible software stand-in with computed parity-signature and residual gate.

    This stand-in computes syndrome_ok by comparing parity signatures `H*c` for observed vs reference
    binary boundary corrections under an identity-H placeholder.
    """
    obs_u = _finite_vec("observed.bulk", observed.bulk)
    obs_b = _finite_vec("observed.boundary", observed.boundary)
    ref_u = _finite_vec("reference.bulk", reference.bulk)
    ref_b = _finite_vec("reference.boundary", reference.boundary)
    if tau != tau or tau in (float("inf"), float("-inf")):
        raise ShieldDenied("tau must be finite")

    t0 = perf_counter_ns()
    correction = tuple(1 if x >= 0.5 else 0 for x in obs_b)
    reference_correction = tuple(1 if x >= 0.5 else 0 for x in ref_b)
    H = tuple(tuple(1 if i == j else 0 for j in range(WIDTH)) for i in range(WIDTH))
    syndrome = _h_mul_mod2(H, correction)
    expected_syndrome = _h_mul_mod2(H, reference_correction)
    syndrome_ok = syndrome == expected_syndrome

    residual = max(
        max(abs(o - r) for o, r in zip(obs_u, ref_u)),
        max(abs(o - r) for o, r in zip(obs_b, ref_b)),
    )
    logical_ok = syndrome_ok and residual <= float(tau)
    latency_ns = perf_counter_ns() - t0

    return DecodeReport(
        syndrome_ok=syndrome_ok,
        logical_ok=logical_ok,
        iterations=1,
        latency_ns=latency_ns,
        residual=float(residual),
    )


def action_requires_live(write: bool, flip: bool, commit: bool) -> bool:
    """Return whether an action touches live membrane state."""
    return write or flip or commit
