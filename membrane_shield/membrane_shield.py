from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from time import time_ns
from typing import FrozenSet, Optional, Tuple, Dict, List
import hmac
import secrets

WIDTH = 32

class Role(str, Enum):
    OBSERVATEUR = 'observateur'
    CALIBRATEUR = 'calibrateur'
    DECODEUR = 'decodeur'
    GARDIEN = 'gardien'

class Face(str, Enum):
    BULK = 'U'
    BOUNDARY = 'B'

class Sector(str, Enum):
    ANY = 'ANY'
    EVEN = 'EVEN'
    ODD = 'ODD'
    FOLD8 = 'FOLD8'

class ShieldDenied(Exception):
    pass

def mu(i: int) -> int:
    return (int(i) + 16) % WIDTH

def sigma(i: int) -> int:
    return (int(i) + 4) % WIDTH

def _finite_vec(name: str, vec) -> tuple:
    if vec is None:
        raise ShieldDenied(f'{name}: missing')
    try:
        out = tuple(float(x) for x in vec)
    except (TypeError, ValueError) as exc:
        raise ShieldDenied(f'{name}: not real-valued') from exc
    if len(out) != WIDTH:
        raise ShieldDenied(f'{name}: width {len(out)} != {WIDTH}')
    if any(x != x or x in (float('inf'), float('-inf')) for x in out):
        raise ShieldDenied(f'{name}: non-finite component')
    return out

def residual_max(observed, reference) -> float:
    obs = _finite_vec('observed', observed)
    ref = _finite_vec('reference', reference)
    return max(abs(o - r) for o, r in zip(obs, ref))

def deltas(observed, reference) -> tuple:
    obs = _finite_vec('observed', observed)
    ref = _finite_vec('reference', reference)
    return tuple(o - r for o, r in zip(obs, ref))

def symmetry_ok(observed, reference, sector: Sector, eps: float) -> bool:
    if sector is Sector.ANY:
        return True
    if eps != eps or eps < 0 or eps == float('inf'):
        raise ShieldDenied('symmetry eps must be finite and >= 0')
    d = deltas(observed, reference)
    if sector is Sector.EVEN:
        sign, pairs = 1.0, [(i, mu(i)) for i in range(WIDTH // 2)]
    elif sector is Sector.ODD:
        sign, pairs = -1.0, [(i, mu(i)) for i in range(WIDTH // 2)]
    elif sector is Sector.FOLD8:
        sign, pairs = 1.0, []
        for k in range(4):
            ring = [(k + 4 * t) % WIDTH for t in range(8)]
            for a, b in zip(ring, ring[1:] + ring[:1]):
                pairs.append((a, b))
    else:
        raise ShieldDenied('unknown sector')
    return all(abs(d[a] - sign * d[b]) <= eps for a, b in pairs)

@dataclass(frozen=True, slots=True)
class Capability:
    role: Role
    agent_id: str
    allowed_faces: FrozenSet
    can_read: bool
    can_propose_calibration: bool
    can_request_flip: bool
    can_commit: bool
    secret: bytes
    issued_ns: int
    expires_ns: int
    def expired(self, now_ns: Optional[int] = None) -> bool:
        return (now_ns or time_ns()) >= self.expires_ns

@dataclass(frozen=True, slots=True)
class MembraneFrame:
    bulk: Tuple
    boundary: Tuple
    @classmethod
    def zeros(cls) -> 'MembraneFrame':
        z = tuple(0.0 for _ in range(WIDTH))
        return cls(bulk=z, boundary=z)
    def snapshot(self) -> 'MembraneFrame':
        return self

@dataclass(slots=True)
class CalibrationProposal:
    proposal_id: str
    agent_id: str
    reference: MembraneFrame
    tau: float
    sealed: bool = False
    countersign_agent: Optional[str] = None

@dataclass(slots=True)
class AuditEvent:
    ns: int
    agent_id: str
    role: str
    action: str
    admitted: bool
    detail: str

@dataclass(slots=True)
class ShieldState:
    live: MembraneFrame = field(default_factory=MembraneFrame.zeros)
    reference: MembraneFrame = field(default_factory=MembraneFrame.zeros)
    tau: float = 0.05
    sector: Sector = Sector.ANY
    symmetry_eps: float = 1e-9
    locked: bool = True
    collapse: bool = False
    pending: Optional[CalibrationProposal] = None
    audit: List[AuditEvent] = field(default_factory=list)

class MembraneShield:
    __slots__ = ('_master', '_token_ttl_ns', '_caps', 'state')
    def __init__(self, master: Optional[bytes] = None, token_ttl_s: int = 3600):
        self._master = master or secrets.token_bytes(32)
        self._token_ttl_ns = int(token_ttl_s * 1e9)
        self._caps: Dict[str, Capability] = {}
        self.state = ShieldState()
    def _audit(self, cap: Optional[Capability], action: str, admitted: bool, detail: str) -> None:
        self.state.audit.append(AuditEvent(time_ns(), cap.agent_id if cap else '-', cap.role.value if cap else '-', action, admitted, detail[:240]))
    def _need(self, cap: Capability, *, flip=False, calib=False, commit=False) -> None:
        if cap.expired():
            raise ShieldDenied('capability expired')
        stored = self._caps.get(cap.agent_id)
        if stored is None or stored.secret != cap.secret or stored.role != cap.role:
            raise ShieldDenied('capability revoked or forged')
        if self.state.collapse and flip:
            raise ShieldDenied('membrane collapsed — shield latched')
        if flip and not cap.can_request_flip:
            raise ShieldDenied('no flip privilege')
        if calib and not cap.can_propose_calibration:
            raise ShieldDenied('no calibration privilege')
        if commit and not cap.can_commit:
            raise ShieldDenied('no commit privilege')
    def issue(self, role: Role, agent_id: str) -> Capability:
        if not agent_id or not agent_id.isprintable() or len(agent_id) > 64:
            raise ShieldDenied('invalid agent_id')
        now = time_ns()
        table = {
            Role.OBSERVATEUR: dict(allowed_faces=frozenset({Face.BOUNDARY}), can_read=True, can_propose_calibration=False, can_request_flip=False, can_commit=False, tag='obs'),
            Role.CALIBRATEUR: dict(allowed_faces=frozenset({Face.BOUNDARY, Face.BULK}), can_read=True, can_propose_calibration=True, can_request_flip=False, can_commit=False, tag='cal'),
            Role.DECODEUR: dict(allowed_faces=frozenset({Face.BOUNDARY}), can_read=True, can_propose_calibration=False, can_request_flip=True, can_commit=False, tag='dec'),
            Role.GARDIEN: dict(allowed_faces=frozenset({Face.BOUNDARY, Face.BULK}), can_read=True, can_propose_calibration=True, can_request_flip=True, can_commit=True, tag='grd'),
        }
        spec = table[role]
        tag = spec.pop('tag')
        cap = Capability(role, agent_id, secret=hmac.new(self._master, f'{tag}|{agent_id}|{now}'.encode(), sha256).digest(), issued_ns=now, expires_ns=now + self._token_ttl_ns, **spec)
        self._caps[agent_id] = cap
        self._audit(cap, 'issue', True, role.value)
        return cap
    def revoke(self, gardien: Capability, agent_id: str) -> None:
        self._need(gardien, commit=True)
        self._caps.pop(agent_id, None)
        self._audit(gardien, 'revoke', True, agent_id)
    def observe(self, cap: Capability, face: Face = Face.BOUNDARY) -> tuple:
        self._need(cap)
        if not cap.can_read:
            self._audit(cap, 'observe', False, 'no read')
            raise ShieldDenied('no read privilege')
        if face not in cap.allowed_faces:
            self._audit(cap, 'observe', False, f'face {face.value} forbidden')
            raise ShieldDenied(f'observateur cannot read face {face.value}')
        src = self.state.live.bulk if face is Face.BULK else self.state.live.boundary
        self._audit(cap, 'observe', True, face.value)
        return src
    def propose_calibration(self, cap: Capability, reference_bulk, reference_boundary, tau: float) -> str:
        self._need(cap, calib=True)
        if tau != tau or tau < 0 or tau == float('inf'):
            raise ShieldDenied('tau must be finite and >= 0')
        ref = MembraneFrame(bulk=_finite_vec('U*', reference_bulk), boundary=_finite_vec('B*', reference_boundary))
        pid = secrets.token_hex(8)
        self.state.pending = CalibrationProposal(proposal_id=pid, agent_id=cap.agent_id, reference=ref, tau=float(tau), sealed=False)
        self._audit(cap, 'propose_calibration', True, f'{pid} tau={tau}')
        return pid
    def countersign_calibration(self, cap: Capability, proposal_id: str) -> None:
        self._need(cap, calib=True)
        p = self.state.pending
        if p is None or p.proposal_id != proposal_id:
            raise ShieldDenied('no such calibration proposal')
        if p.agent_id == cap.agent_id and cap.role is not Role.GARDIEN:
            raise ShieldDenied('dual-control: same agent cannot countersign')
        p.sealed = True
        p.countersign_agent = cap.agent_id
        self._audit(cap, 'countersign', True, proposal_id)
    def commit_calibration(self, gardien: Capability, proposal_id: str) -> None:
        self._need(gardien, commit=True)
        p = self.state.pending
        if p is None or p.proposal_id != proposal_id:
            raise ShieldDenied('no such calibration proposal')
        if not p.sealed:
            raise ShieldDenied('calibration not sealed — dual-control required')
        self.state.reference = p.reference
        self.state.tau = p.tau
        self.state.pending = None
        self.state.locked = False
        self._audit(gardien, 'commit_calibration', True, proposal_id)
    def set_sector(self, gardien: Capability, sector: Sector, eps: Optional[float] = None) -> None:
        self._need(gardien, commit=True)
        if not isinstance(sector, Sector):
            raise ShieldDenied('unknown sector')
        if eps is not None:
            if eps != eps or eps < 0 or eps == float('inf'):
                raise ShieldDenied('symmetry eps must be finite and >= 0')
            self.state.symmetry_eps = float(eps)
        self.state.sector = sector
        self._audit(gardien, 'set_sector', True, sector.value)
    def request_flip(self, cap: Capability, new_boundary, *, syndrome_ok: bool, logical_ok: bool = True) -> MembraneFrame:
        self._need(cap, flip=True)
        if self.state.locked:
            self._audit(cap, 'flip', False, 'shield locked')
            raise ShieldDenied('shield locked until calibration is committed')
        if not syndrome_ok:
            self._audit(cap, 'flip', False, 'syndrome rejected')
            raise ShieldDenied('syndrome not admitted (Hc != s)')
        if not logical_ok:
            self._audit(cap, 'flip', False, 'logical check failed')
            raise ShieldDenied('logical operator would be flipped')
        proposed_b = _finite_vec("B'", new_boundary)
        delta = tuple(pb - ob for pb, ob in zip(proposed_b, self.state.live.boundary))
        proposed_u = tuple(u + d for u, d in zip(self.state.live.bulk, delta))
        agg = max(residual_max(proposed_b, self.state.reference.boundary), residual_max(proposed_u, self.state.reference.bulk))
        if agg > self.state.tau:
            self.state.collapse = True
            self._audit(cap, 'flip', False, f'residual {agg} > tau {self.state.tau}')
            raise ShieldDenied('residual breach — shield latched (collapse)')
        eps = self.state.symmetry_eps
        if not symmetry_ok(proposed_b, self.state.reference.boundary, self.state.sector, eps):
            self._audit(cap, 'flip', False, f'symmetry {self.state.sector.value} failed')
            raise ShieldDenied(f'symmetry not admitted ({self.state.sector.value})')
        if not symmetry_ok(proposed_u, self.state.reference.bulk, self.state.sector, eps):
            self._audit(cap, 'flip', False, f'symmetry bulk {self.state.sector.value} failed')
            raise ShieldDenied(f'symmetry not admitted on bulk ({self.state.sector.value})')
        self.state.live = MembraneFrame(bulk=proposed_u, boundary=proposed_b)
        self._audit(cap, 'flip', True, f'residual={agg:.6g}')
        return self.state.live.snapshot()
    def latch(self, gardien: Capability, reason: str = 'manual') -> None:
        self._need(gardien, commit=True)
        self.state.collapse = True
        self.state.locked = True
        self._audit(gardien, 'latch', True, reason)
    def reset_after_latch(self, gardien: Capability) -> None:
        self._need(gardien, commit=True)
        self.state.live = self.state.reference.snapshot()
        self.state.collapse = False
        self.state.locked = False
        self.state.pending = None
        self._audit(gardien, 'reset', True, 'restored to reference')

def zeros():
    return [0.0] * WIDTH

def bump(vec, i, value):
    out = list(vec)
    out[i] = value
    return out
