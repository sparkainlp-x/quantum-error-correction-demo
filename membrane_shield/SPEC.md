# OES-32 Membrane Shield — Core Specifications

> **Module**: `membrane_shield/membrane_shield.py`  
> **Spec version**: 1.0  
> **Source system**: OES-32 Quantum Holographic QECC

---

## 1. Constants

| Name    | Value | Meaning |
|---------|-------|---------|
| `WIDTH` | `32`  | Fixed dimensionality of every state vector (bulk and boundary). All vectors must be exactly 32 real-valued, finite components. |

---

## 2. Enumerations

### 2.1 `Role`

Four mutually exclusive principal roles. A capability carries exactly one role.

| Role           | String value    | Purpose |
|----------------|-----------------|---------|
| `OBSERVATEUR`  | `observateur`   | Read-only observer of the boundary face |
| `CALIBRATEUR`  | `calibrateur`   | Can read both faces and propose calibrations |
| `DECODEUR`     | `decodeur`      | Can read the boundary face and request flips |
| `GARDIEN`      | `gardien`       | Full control: read all faces, calibrate, flip, commit, latch, reset, revoke |

### 2.2 `Face`

| Face       | Value | Description |
|------------|-------|-------------|
| `BULK`     | `U`   | Interior (bulk) state vector |
| `BOUNDARY` | `B`   | Boundary state vector |

### 2.3 `Sector`

Symmetry mode applied to the flip admission gate (see §6).

| Sector  | Value   | Constraint on delta vector `d = B' − B*` (and `U' − U*`) |
|---------|---------|----------------------------------------------------------|
| `ANY`   | `ANY`   | No symmetry check; all vectors admitted |
| `EVEN`  | `EVEN`  | `d[i] == d[mu(i)]` for all `i` in `0..15` |
| `ODD`   | `ODD`   | `d[i] == -d[mu(i)]` for all `i` in `0..15` |
| `FOLD8` | `FOLD8` | `d[a] == d[b]` for every consecutive pair `(a,b)` in each 8-element ring |

---

## 3. Index Maps

```
mu(i)    = (i + 16) % 32     # antipodal reflection
sigma(i) = (i +  4) % 32     # quarter-period shift
```

`mu` pairs index `i` with its antipodal counterpart. Used by `EVEN` and `ODD` symmetry checks.

`sigma` defines a quarter-period cyclic shift. Available as a helper; not used in the current admission pipeline.

---

## 4. Capability Model

### 4.1 Issuance

`MembraneShield.issue(role, agent_id) → Capability`

- `agent_id` must be non-empty, printable (all chars pass `str.isprintable()`), and at most 64 characters long. Violation raises `ShieldDenied`.
- Each issued `Capability` holds an HMAC-SHA-256 secret derived from the shield's master key, the role tag, the `agent_id`, and the issuance timestamp. Forgery of the secret is computationally infeasible.
- Issuing a new capability for an existing `agent_id` overwrites the previous one (re-keying).
- A capability expires at `issued_ns + token_ttl_ns` (default TTL: 3 600 s).

### 4.2 Revocation

`MembraneShield.revoke(gardien, agent_id)`

- Requires `gardien` with `can_commit=True` (i.e., `Role.GARDIEN`).
- Immediately removes the named agent's capability from the active registry. Any further use of the old capability object raises `ShieldDenied`.

### 4.3 Capability Permission Matrix

| Capability flag          | OBSERVATEUR | CALIBRATEUR | DECODEUR | GARDIEN |
|--------------------------|:-----------:|:-----------:|:--------:|:-------:|
| `can_read`               | ✓           | ✓           | ✓        | ✓       |
| `allowed_faces` includes BOUNDARY | ✓  | ✓           | ✓        | ✓       |
| `allowed_faces` includes BULK     | —  | ✓           | —        | ✓       |
| `can_propose_calibration`| —           | ✓           | —        | ✓       |
| `can_request_flip`       | —           | —           | ✓        | ✓       |
| `can_commit`             | —           | —           | —        | ✓       |

### 4.4 Capability Validation (`_need`)

Every protected operation calls `_need` which enforces, in order:

1. The capability has not expired (`expires_ns > now_ns`).
2. The stored registry entry for `agent_id` matches the presented capability's `secret` and `role` exactly — forged or stale objects are rejected.
3. For flip requests: if `state.collapse` is `True`, the request is rejected with `'membrane collapsed — shield latched'`.
4. Required privilege flags are checked (`can_request_flip`, `can_propose_calibration`, `can_commit`).

---

## 5. State Model (`ShieldState`)

```
ShieldState
  live          MembraneFrame   current live state
  reference     MembraneFrame   committed reference (set by calibration)
  tau           float           residual tolerance  (default: 0.05)
  sector        Sector          active symmetry mode (default: ANY)
  symmetry_eps  float           symmetry tolerance  (default: 1e-9)
  locked        bool            True → flips blocked (default: True)
  collapse      bool            True → shield latched after residual breach
  pending       CalibrationProposal | None
  audit         List[AuditEvent]
```

**Initial state**: `locked=True`, `collapse=False`, all vectors zero, `tau=0.05`, `sector=ANY`.  
The shield starts locked. A committed calibration is required before any flip can be admitted.

---

## 6. Vector Rules

A vector is **valid** if and only if:
- It is iterable and all elements convert to `float` without error.
- Its length is exactly `WIDTH` (32).
- No component is `NaN` or ±∞.

Violation of any rule raises `ShieldDenied` immediately; the operation is aborted without state change.

---

## 7. Calibration Protocol (Dual-Control)

The calibration protocol sets the reference frame and tolerance for all subsequent flip admissions. It requires at least two distinct agents (dual-control) unless a `GARDIEN` self-countersigns.

### Steps

1. **Propose** — `propose_calibration(cap, reference_bulk, reference_boundary, tau)`
   - Requires `can_propose_calibration=True`.
   - `tau` must be finite and `≥ 0`; `NaN`, negative, or infinite values raise `ShieldDenied`.
   - Both reference vectors must satisfy the vector rules (§6).
   - Creates a `CalibrationProposal` in `state.pending` with `sealed=False`.
   - Returns a random 8-byte hex `proposal_id`.

2. **Countersign** — `countersign_calibration(cap, proposal_id)`
   - Requires `can_propose_calibration=True`.
   - `proposal_id` must match `state.pending.proposal_id`; otherwise `ShieldDenied`.
   - **Dual-control rule**: if `cap.agent_id == proposal.agent_id` and `cap.role != GARDIEN`, the countersign is rejected (`'dual-control: same agent cannot countersign'`). A `GARDIEN` may self-countersign.
   - Sets `proposal.sealed = True` and records `countersign_agent`.

3. **Commit** — `commit_calibration(gardien, proposal_id)`
   - Requires `can_commit=True` (GARDIEN only).
   - Proposal must be sealed; an unsealed proposal raises `ShieldDenied`.
   - Atomically: sets `state.reference`, `state.tau`, clears `state.pending`, and sets `state.locked = False`.

### Post-commit invariants

- `state.locked` is `False`.
- `state.reference` equals the committed reference frame.
- `state.tau` equals the committed tolerance.
- `state.pending` is `None`.

---

## 8. Flip Admission Pipeline

`request_flip(cap, new_boundary, *, syndrome_ok, logical_ok=True) → MembraneFrame`

Requires `can_request_flip=True`. All checks are performed in strict order; the first failure raises `ShieldDenied` and no state change occurs (except collapse is set on residual breach).

### 8.1 Gate sequence

| # | Gate | Failure message |
|---|------|-----------------|
| 1 | Capability valid (§4.4) | various |
| 2 | `state.locked == False` | `'shield locked until calibration is committed'` |
| 3 | `syndrome_ok == True` | `'syndrome not admitted (Hc != s)'` |
| 4 | `logical_ok == True` | `'logical operator would be flipped'` |
| 5 | New boundary vector valid (§6) | various |
| 6 | `residual(B', U') ≤ tau` | `'residual breach — shield latched (collapse)'` — also sets `state.collapse = True` |
| 7 | `symmetry_ok(B', B*, sector, eps)` | `'symmetry not admitted (<sector>)'` |
| 8 | `symmetry_ok(U', U*, sector, eps)` | `'symmetry not admitted on bulk (<sector>)'` |

### 8.2 Derived vectors

Given `new_boundary` B′ and current live state `(B_live, U_live)`:

```
delta[i]  = B'[i] − B_live[i]         # boundary shift
U'[i]     = U_live[i] + delta[i]      # bulk tracks boundary
```

### 8.3 Residual computation

```
agg = max(
    max|B'[i] − B*[i]|,    # boundary vs reference
    max|U'[i] − U*[i]|     # bulk vs reference
)
```

If `agg > tau`, the shield **collapses** (`state.collapse = True`) and the flip is denied. The shield remains latched until `reset_after_latch` is called by a GARDIEN.

### 8.4 Symmetry gate

Applied to both `(B', B*)` and `(U', U*)` using the active `state.sector` and `state.symmetry_eps`.  
See §2.3 for sector-specific constraints.  
The residual gate (§8.3) runs **before** the symmetry gate; a residual breach will latch the shield even if symmetry would have passed.

### 8.5 On admission

- `state.live` is updated to `MembraneFrame(bulk=U', boundary=B')`.
- Returns `state.live.snapshot()` (the new live frame).
- An audit event with `admitted=True` and `detail='residual=<agg>'` is appended.

---

## 9. Sector Configuration

`set_sector(gardien, sector, eps=None)`

- Requires `can_commit=True`.
- `sector` must be a `Sector` enum member; unknown values raise `ShieldDenied`.
- If `eps` is supplied it must be finite and `≥ 0`; invalid values raise `ShieldDenied`.
- Takes effect immediately; subsequent flips use the new sector and eps.

---

## 10. Latch and Reset

### 10.1 Manual latch

`latch(gardien, reason='manual')`

- Requires `can_commit=True`.
- Sets `state.collapse = True` and `state.locked = True`.
- Blocks all subsequent flip requests until reset.

### 10.2 Reset after latch

`reset_after_latch(gardien)`

- Requires `can_commit=True`.
- Restores `state.live` to `state.reference.snapshot()`.
- Clears `state.collapse` and `state.locked` to `False`.
- Clears `state.pending`.
- Does **not** change `state.reference`, `state.tau`, `state.sector`, or `state.symmetry_eps`.

---

## 11. Observation

`observe(cap, face=Face.BOUNDARY) → tuple`

- Requires `can_read=True` (all roles satisfy this).
- `face` must be in `cap.allowed_faces`; an out-of-scope face raises `ShieldDenied`.
- Returns the corresponding vector from `state.live` (boundary or bulk). The vector is returned by reference — callers must not mutate it.

---

## 12. Audit Trail

Every operation that succeeds or fails appends an `AuditEvent` to `state.audit`:

```
AuditEvent
  ns          int     nanosecond timestamp (time_ns())
  agent_id    str     agent who triggered the operation ('-' if none)
  role        str     role value string ('-' if none)
  action      str     operation name (e.g. 'issue', 'flip', 'latch')
  admitted    bool    True if the operation succeeded
  detail      str     truncated to 240 characters
```

The audit log is append-only and grows monotonically. No operation removes entries.

---

## 13. Error Model

All errors raised by this module are instances of `ShieldDenied(Exception)`.

| Category | Trigger |
|----------|---------|
| Invalid input | Bad `agent_id`, non-finite vector component, wrong vector width, `NaN`/±∞ tau or eps |
| Expired capability | `cap.expires_ns ≤ now_ns` |
| Revoked / forged capability | Secret or role mismatch in registry |
| Privilege denied | Role lacks required permission flag |
| Shield locked | `state.locked == True` on flip request |
| Shield collapsed | `state.collapse == True` on flip request |
| Syndrome rejected | `syndrome_ok == False` |
| Logical check failed | `logical_ok == False` |
| Residual breach | `agg > tau` (also sets `state.collapse = True`) |
| Symmetry violation | Delta vector fails sector constraint |
| Dual-control violation | Same non-GARDIEN agent proposes and countersigns |
| No proposal | `state.pending` is `None` or `proposal_id` mismatch |
| Unsealed proposal | `commit_calibration` called before `countersign_calibration` |

No `ShieldDenied` ever leaks internal key material or audit content.

---

## 14. Security Properties

1. **HMAC capability binding** — Capability secrets are HMAC-SHA-256 values keyed on the shield's master secret. Presented capabilities are verified against the stored registry copy; any bit-flip in `secret` or `role` is rejected.
2. **Capability isolation** — Re-issuing a capability for an `agent_id` immediately invalidates the previous object; no revocation race exists.
3. **Dual-control on calibration** — The reference frame and tolerance can only change through a two-party process (propose + countersign by different agents, or by a GARDIEN alone), guarded by a GARDIEN commit. This prevents single-point manipulation of the admission threshold.
4. **Collapse latch** — A residual breach permanently blocks further flips until a GARDIEN explicitly resets the shield. There is no self-recovery path.
5. **Audit completeness** — Every call to a protected method appends at least one audit event, whether admitted or denied, before returning or raising.

---

## 15. Running Tests

```bash
# Core shield unit tests (52 tests)
cd membrane_shield && python3 -m unittest test_shield.py -v

# Monte Carlo validation tests (42 tests)
cd membrane_shield && python3 -m unittest test_monte_carlo.py -v

# Monte Carlo sweep (CLI)
cd membrane_shield && python3 monte_carlo.py --trials 1000
```
