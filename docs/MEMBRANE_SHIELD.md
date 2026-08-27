# Membrane Shield

The membrane shield is a fail-closed authorization and admission-control layer for the
Spark membrane stack spanning OES-32 simulation logic and decoder integration.

## Required Invariants
- Width is fixed at 32 for protected vectors and membrane faces.
- Non-finite float inputs (NaN/Inf) are rejected.
- Observateur reads boundary copies only, never bulk aliases.
- Calibration is dual-control: one agent proposes, a different agent countersigns, and only gardien commits.
- Flip is admitted only when computed syndrome proof (`Hc == s`) is valid, residual remains within `tau`, and `symmetry_sector(B', B*)` matches the declared pattern.
- Residual breach latches collapse and blocks further flips until gardien reset to sealed reference.

## Operational Roles
- `observateur`: read-only copy access to boundary.
- `calibrateur`: quarantine calibration proposals only.
- `decodeur`: flip requests subject to admission checks.
- `gardien`: commit, revoke, latch, and reset authority.

## Safety Position
This shield implements software policy controls and decoder gating only.
It does not make claims about gravity, medical treatment, or physical-device behavior.
